"""RSS 抓取：解析 feed，返回统一的条目列表。"""

from datetime import datetime, timezone
from typing import Optional

import feedparser

from src.utils.http import fetch


def _parse_date(entry) -> Optional[datetime]:
    """从 feedparser 条目中取发布时间，返回带时区(UTC)的 datetime。"""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def fetch_rss(url: str, max_items: int = 30) -> list[dict]:
    """抓取并解析 RSS，返回 list[dict]，字段：title、url、summary、published_at。"""
    text = fetch(url)
    if not text:
        return []

    feed = feedparser.parse(text)
    items: list[dict] = []
    for entry in feed.entries[:max_items]:
        items.append(
            {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "summary": entry.get("summary", "")[:500],
                "published_at": _parse_date(entry),
            }
        )
    return items
