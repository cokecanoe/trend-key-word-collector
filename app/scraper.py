import re
import time
import logging
from collections import Counter

import requests
from pytrends.request import TrendReq

from database import save_reddit_keywords, save_google_trends

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

SUBREDDITS = ['streetwear', 'hiphopfashion', 'japanesestreetwear', 'Lookbook']

GOOGLE_SEEDS = [
    'streetwear',
    'Japanese streetwear',
    'oversized hoodie',
    'graphic tee',
    'dad cap',
    'techwear',
    'harajuku fashion',
    'cherry blossom clothing',
]

STOP_WORDS = {
    # Articles / determiners
    'the', 'this', 'that', 'these', 'those', 'some', 'any', 'all', 'both',
    # Pronouns
    'i', 'me', 'my', 'mine', 'we', 'our', 'you', 'your', 'he', 'she', 'it',
    'his', 'her', 'its', 'they', 'them', 'their',
    # Common verbs
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'may', 'might',
    'must', 'can', 'could', 'get', 'got', 'getting', 'just', 'let',
    # Prepositions / conjunctions
    'in', 'on', 'at', 'by', 'for', 'with', 'about', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'from', 'up', 'down',
    'out', 'off', 'over', 'under', 'and', 'but', 'or', 'nor', 'so', 'yet',
    'than', 'also', 'then', 'too', 'very', 'more',
    # Common filler
    'not', 'no', 'only', 'own', 'same', 'here', 'there', 'when', 'where',
    'how', 'what', 'which', 'who', 'why', 'even', 'still', 'now', 'new',
    'old', 'one', 'two', 'first', 'last', 'long', 'time', 'way', 'back',
    # Reddit-specific noise
    'anyone', 'help', 'question', 'questions', 'discussion', 'weekly',
    'monthly', 'looking', 'really', 'think', 'know', 'want', 'need',
    'like', 'going', 'used', 'using', 'see', 'seen', 'say', 'said',
    'come', 'came', 'good', 'bad', 'well', 'such', 'much', 'many',
    'lot', 'bit', 'thing', 'things', 'kind', 'type', 'guy', 'guys',
    'find', 'found', 'make', 'made', 'best', 'give', 'use',
}

HEADERS = {'User-Agent': 'KarasuTrendBot/1.0 (karasuapparel.ca)'}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r'[a-zA-Z]+', text.lower())
    return [w for w in words if len(w) >= 4 and w not in STOP_WORDS]


def scrape_reddit() -> list[tuple[str, int]]:
    log.info('Starting Reddit scrape...')
    all_words: list[str] = []

    for sub in SUBREDDITS:
        for sort, timeframe in [('top', 'week'), ('hot', '')]:
            url = f'https://www.reddit.com/r/{sub}/{sort}.json?limit=100'
            if timeframe:
                url += f'&t={timeframe}'
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    posts = resp.json()['data']['children']
                    for post in posts:
                        title = post['data'].get('title', '')
                        all_words.extend(_tokenize(title))
                    log.info('  r/%s (%s): %d posts', sub, sort, len(posts))
                else:
                    log.warning('  r/%s (%s): HTTP %s', sub, sort, resp.status_code)
            except Exception as exc:
                log.warning('  r/%s (%s) failed: %s', sub, sort, exc)
            time.sleep(2)

    counter = Counter(all_words)
    top = counter.most_common(50)
    log.info('Reddit scrape complete — %d unique keywords', len(counter))
    return top


def scrape_google_trends() -> list[dict]:
    log.info('Starting Google Trends scrape...')
    results: list[dict] = []

    try:
        pytrends = TrendReq(hl='en-US', tz=300, timeout=(10, 25))
    except Exception as exc:
        log.error('Could not initialise pytrends: %s', exc)
        return results

    for seed in GOOGLE_SEEDS:
        try:
            pytrends.build_payload([seed], timeframe='now 7-d', geo='')
            related = pytrends.related_queries()
            for trend_type in ('rising', 'top'):
                df = related.get(seed, {}).get(trend_type)
                if df is not None and not df.empty:
                    for _, row in df.head(10).iterrows():
                        results.append({
                            'seed': seed,
                            'related': row['query'],
                            'value': int(row['value']),
                            'type': trend_type,
                        })
            log.info('  "%s": %d related queries', seed, len(results))
        except Exception as exc:
            log.warning('  Google Trends "%s" failed: %s', seed, exc)
        time.sleep(6)

    log.info('Google Trends scrape complete — %d results', len(results))
    return results


def run_scraper():
    log.info('=== Scraper run started ===')

    try:
        reddit_data = scrape_reddit()
        if reddit_data:
            save_reddit_keywords(reddit_data)
    except Exception as exc:
        log.error('Reddit scrape failed: %s', exc)

    try:
        trends_data = scrape_google_trends()
        if trends_data:
            save_google_trends(trends_data)
    except Exception as exc:
        log.error('Google Trends scrape failed: %s', exc)

    log.info('=== Scraper run complete ===')
