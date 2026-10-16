"""公开 API 抓取（Hacker News）。"""

import json
from datetime import datetime, timezone

from src.utils.http import fetch

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


def fetch_hn_top(limit: int = 30) -> list[dict]:
    """抓取 HN top stories，返回 list[dict]，字段：title、url、summary、published_at、author、heat_score。"""
    ids_text = fetch(HN_TOP_URL)
    if not ids_text:
        return []

    try:
        ids = json.loads(ids_text)[:limit]
    except (json.JSONDecodeError, TypeError):
        return []

    items: list[dict] = []
    for item_id in ids:
        detail_text = fetch(HN_ITEM_URL.format(item_id=item_id))
        if not detail_text:
            continue
        try:
            data = json.loads(detail_text)
        except json.JSONDecodeError:
            continue
        if data.get("type") != "story":
            continue

        published = None
        if data.get("time"):
            published = datetime.fromtimestamp(data["time"], tz=timezone.utc)

        items.append(
            {
                "title": data.get("title", ""),
                "url": data.get("url")
                or f"https://news.ycombinator.com/item?id={item_id}",
                "summary": "",
                "published_at": published,
                "author": data.get("by", ""),
                # HN 热度：score / 500，封顶 1.0
                "heat_score": min(data.get("score", 0) / 500, 1.0),
            }
        )
    return items
