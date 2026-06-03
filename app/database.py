import json
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.environ.get('DB_PATH', '/app/data/trends.db')


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    _ensure_data_dir()
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reddit_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                count INTEGER NOT NULL,
                subreddit TEXT,
                collected_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS google_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed TEXT NOT NULL,
                related_keyword TEXT NOT NULL,
                trend_value INTEGER NOT NULL,
                trend_type TEXT NOT NULL,
                collected_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS content_briefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_angle TEXT,
                hook TEXT,
                text_overlays TEXT,
                voiceover_script TEXT,
                caption TEXT,
                hashtags TEXT,
                generated_at TEXT NOT NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_reddit_collected ON reddit_keywords(collected_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trends_collected ON google_trends(collected_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_briefs_generated ON content_briefs(generated_at)')


def save_reddit_keywords(keywords: list[tuple[str, int]]):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.executemany(
            'INSERT INTO reddit_keywords (keyword, count, collected_at) VALUES (?, ?, ?)',
            [(kw, count, now) for kw, count in keywords]
        )


def save_google_trends(trends: list[dict]):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.executemany(
            'INSERT INTO google_trends (seed, related_keyword, trend_value, trend_type, collected_at) VALUES (?, ?, ?, ?, ?)',
            [(t['seed'], t['related'], t['value'], t['type'], now) for t in trends]
        )


def save_content_brief(brief: dict):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            '''INSERT INTO content_briefs
               (content_angle, hook, text_overlays, voiceover_script, caption, hashtags, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                brief.get('content_angle', ''),
                brief.get('hook', ''),
                json.dumps(brief.get('text_overlays', [])),
                brief.get('voiceover_script', ''),
                brief.get('caption', ''),
                json.dumps(brief.get('hashtags', [])),
                now,
            ),
        )


def get_latest_brief() -> dict | None:
    if not os.path.exists(DB_PATH):
        return None
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM content_briefs ORDER BY generated_at DESC LIMIT 1'
        ).fetchone()
        if not row:
            return None
        brief = dict(row)
        brief['text_overlays'] = json.loads(brief['text_overlays'])
        brief['hashtags'] = json.loads(brief['hashtags'])
        return brief


def get_latest_data() -> dict:
    _ensure_data_dir()
    if not os.path.exists(DB_PATH):
        return {'reddit_keywords': [], 'google_trends': [], 'last_updated': None, 'status': 'pending'}

    with get_db() as conn:
        latest_reddit = conn.execute(
            'SELECT MAX(collected_at) as ts FROM reddit_keywords'
        ).fetchone()['ts']

        reddit_keywords = []
        if latest_reddit:
            rows = conn.execute(
                '''SELECT keyword, count FROM reddit_keywords
                   WHERE collected_at = ? ORDER BY count DESC LIMIT 40''',
                (latest_reddit,)
            ).fetchall()
            reddit_keywords = [dict(r) for r in rows]

        latest_trends = conn.execute(
            'SELECT MAX(collected_at) as ts FROM google_trends'
        ).fetchone()['ts']

        google_trends = []
        if latest_trends:
            rows = conn.execute(
                '''SELECT seed, related_keyword, trend_value FROM google_trends
                   WHERE collected_at = ? ORDER BY trend_value DESC LIMIT 40''',
                (latest_trends,)
            ).fetchall()
            google_trends = [dict(r) for r in rows]

        return {
            'reddit_keywords': reddit_keywords,
            'google_trends': google_trends,
            'last_updated': latest_reddit,
            'status': 'ok' if reddit_keywords or google_trends else 'pending',
            'content_brief': get_latest_brief(),
        }
