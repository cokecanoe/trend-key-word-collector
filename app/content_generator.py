import json
import logging
import os

import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a social media content strategist for Karasu Apparel, a Japanese-inspired streetwear brand based in Calgary, Canada.

Brand identity:
- Name: Karasu (crow in Japanese)
- Aesthetic: minimal, black and white, Japanese streetwear
- Products: hoodies ($75-95 CAD), heavyweight graphic tees, dad caps (~$45-50 CAD)
- Logo: flat black crow silhouette with cherry blossom back graphic
- Vibe: clean, confident, Japanese street culture — not loud, not hype-beast
- Platform: TikTok faceless account — no person on camera, text-on-video style

Your job is to generate TikTok content briefs based on real trending streetwear keywords. Content should feel native to TikTok — thumb-stopping hooks, short punchy overlays, trend-aware but true to the brand.

Respond with valid JSON only. No markdown, no explanation."""


def generate_content_brief(reddit_keywords: list[dict], google_trends: list[dict]) -> dict | None:
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        log.warning('ANTHROPIC_API_KEY not set — skipping content generation')
        return None

    client = anthropic.Anthropic(api_key=api_key)

    top_reddit = [kw['keyword'] for kw in reddit_keywords[:20]]
    top_trends = [
        f"{t['related_keyword']} (from \"{t['seed']}\")"
        for t in google_trends[:15]
    ]

    user_prompt = f"""Current streetwear trend data:

TOP REDDIT KEYWORDS this week:
{', '.join(top_reddit)}

RISING GOOGLE SEARCHES:
{chr(10).join(f'- {t}' for t in top_trends)}

Generate a TikTok content brief for Karasu Apparel using this exact JSON structure:

{{
  "content_angle": "One sentence — what is this video about and why will people watch",
  "hook": "First 3 seconds on screen — max 8 words, must stop the scroll",
  "text_overlays": [
    "overlay line 1",
    "overlay line 2",
    "overlay line 3",
    "overlay line 4",
    "overlay line 5"
  ],
  "voiceover_script": "Full 30-45 second script for an AI voice to read. Conversational, confident, not salesy.",
  "caption": "TikTok caption under 150 characters",
  "hashtags": ["#hashtag1", "#hashtag2"]
}}

Rules:
- Hook must create curiosity or tension immediately
- Each text overlay = 3-6 words, shown one at a time on screen
- Voiceover should sound like a knowledgeable friend, not an ad
- 15-20 hashtags: mix broad (#streetwear, #fashion) with niche (#japanesestreetwear, #karasuapparel, #crowapparel)
- Lean into the crow / Japanese aesthetic naturally where it fits — never force it"""

    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            system=[
                {
                    'type': 'text',
                    'text': SYSTEM_PROMPT,
                    'cache_control': {'type': 'ephemeral'},
                }
            ],
            messages=[{'role': 'user', 'content': user_prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if model wraps in them
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0]

        brief = json.loads(raw)
        log.info('Content brief generated successfully')
        return brief

    except json.JSONDecodeError as exc:
        log.error('Failed to parse brief JSON: %s', exc)
        return None
    except Exception as exc:
        log.error('Content generation failed: %s', exc)
        return None
