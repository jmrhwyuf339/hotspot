"""入口：遍历 sources.yaml，抓取 → 过滤 → 打分 → 去重写入 SQLite（hotspot.db）。"""

import sys
import time
from datetime import datetime, timedelta, timezone

from src.config import get_interest, load_interests, load_sources
from src.db import init_db
from src.fetchers.api_fetcher import fetch_hn_top
from src.fetchers.rss_fetcher import fetch_rss
from src.processors.dedup import url_hash
from src.processors.filter import match_interest
from src.processors.scorer import calc_final_score, get_source_quality
from src.utils.translator import translate_text

MAX_ITEMS = 30
MAX_AGE_DAYS = 30     # 发布时间距今超过这么多天的条目直接丢弃


def is_stale(item: dict) -> bool:
    """published_at 存在且距今超过 MAX_AGE_DAYS 天 → 过期（写库前丢弃）。"""
    published_at = item.get("published_at")
    if not published_at:
        return False
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - published_at > timedelta(days=MAX_AGE_DAYS)


# 需要把标题翻译成中文的源（英文源）
TRANSLATE_URL_MARKERS = ("hacker-news", "techcrunch")


def needs_translation(source: dict) -> bool:
    """HN / TechCrunch 这类英文源的标题需要翻译。"""
    url = (source.get("url") or "").lower()
    return any(marker in url for marker in TRANSLATE_URL_MARKERS)


def translate_title(title: str) -> str:
    """标题 → 「[译] 中文标题 (英文原标题)」；翻译失败时原样返回。"""
    translated = translate_text(title)
    if not translated or translated == title:
        return title
    return f"[译] {translated} ({title})"


def fetch_items(source: dict) -> list[dict]:
    """按 source 的 type 选择抓取方式。"""
    stype = source.get("type")
    if stype == "rss":
        return fetch_rss(source["url"], max_items=MAX_ITEMS)
    if stype == "api" and "hacker-news" in source["url"]:
        return fetch_hn_top(limit=MAX_ITEMS)
    raise ValueError(f"unsupported source type: {stype} ({source.get('url')})")


def main() -> None:
    # 保证中文在 Windows 终端 / 重定向时都按 UTF-8 输出，避免乱码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    interests = load_interests()
    sources = load_sources()
    conn = init_db()

    total_added = total_filtered = total_stale = total_skipped = 0

    for source in sources:
        name = source.get("name") or source.get("url", "?")
        interest = get_interest(interests, source.get("interest"))

        # 来源质量分：按 user_feedback 里的 like / hide 动态计算（阶段八）
        quality = get_source_quality(name, conn)
        print(f"[fetch] {name} ({source.get('type')}) | 来源质量分 {quality}")

        if interest is None:
            print(f"  [warn] 找不到兴趣「{source.get('interest')}」，跳过该源")
            continue

        # 单源失败不影响其他源
        try:
            items = fetch_items(source)
        except Exception as e:  # noqa: BLE001
            print(f"  [error] 抓取失败：{e}")
            continue

        if not items:
            print("  [warn] 未抓到条目（可能被拒绝或网络失败）")
            continue

        # 英文源：先翻译标题（再过滤关键词），每条之间 sleep 1 秒
        if needs_translation(source):
            print(f"  [translate] 翻译 {len(items)} 条标题 …")
            for item in items:
                item["title"] = translate_title(item["title"])
                time.sleep(1)
            done = sum(1 for it in items if it["title"].startswith("[译]"))
            print(f"  [translate] 完成：{done}/{len(items)} 条已译成中文")

        added = filtered = stale = skipped = 0

        for item in items:
            # 1) 兴趣过滤
            if not match_interest(item, interest):
                filtered += 1
                continue

            # 2) 过期过滤：发布时间距今超过 30 天则丢弃（不写库）
            if is_stale(item):
                stale += 1
                continue

            # 3) 去重（与阶段二逻辑一致）
            uh = url_hash(item["url"])
            exists = conn.execute(
                "SELECT 1 FROM items WHERE url_hash = ? LIMIT 1", (uh,)
            ).fetchone()
            if exists:
                skipped += 1
                continue

            # 4) 打分 + 写入
            final = calc_final_score(item, interest["weight"], quality)
            published_at = item.get("published_at")
            conn.execute(
                """
                INSERT INTO items
                    (title, url, url_hash, summary, author, published_at,
                     final_score, interest, source_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["title"],
                    item["url"],
                    uh,
                    item.get("summary"),
                    item.get("author"),
                    published_at.isoformat() if published_at else None,
                    final,
                    interest["name"],
                    name,
                ),
            )
            added += 1

        conn.commit()
        print(
            f"  新增 {added} 条 / 过滤掉 {filtered} 条 / "
            f"过期 {stale} 条 / 跳过 {skipped} 条"
        )
        total_added += added
        total_filtered += filtered
        total_stale += stale
        total_skipped += skipped

    conn.close()
    print(
        f"总计：新增 {total_added} 条，过滤掉 {total_filtered} 条，"
        f"过期 {total_stale} 条，跳过 {total_skipped} 条"
    )


if __name__ == "__main__":
    main()
