"""入口：遍历 sources.yaml，抓取 → 过滤 → 打分 → 去重写入 SQLite（hotspot.db）。"""

import sys

from src.config import get_interest, load_interests, load_sources
from src.db import init_db
from src.fetchers.api_fetcher import fetch_hn_top
from src.fetchers.rss_fetcher import fetch_rss
from src.processors.dedup import url_hash
from src.processors.filter import match_interest
from src.processors.scorer import calc_final_score

MAX_ITEMS = 30
SOURCE_QUALITY = 1.0  # 阶段三先固定为 1.0


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

    total_added = total_filtered = total_skipped = 0

    for source in sources:
        name = source.get("name") or source.get("url", "?")
        interest = get_interest(interests, source.get("interest"))

        print(f"[fetch] {name} ({source.get('type')})")

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

        added = filtered = skipped = 0

        for item in items:
            # 1) 兴趣过滤
            if not match_interest(item, interest):
                filtered += 1
                continue

            # 2) 去重（与阶段二逻辑一致）
            uh = url_hash(item["url"])
            exists = conn.execute(
                "SELECT 1 FROM items WHERE url_hash = ? LIMIT 1", (uh,)
            ).fetchone()
            if exists:
                skipped += 1
                continue

            # 3) 打分 + 写入
            final = calc_final_score(item, interest["weight"], SOURCE_QUALITY)
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
        print(f"  新增 {added} 条 / 过滤掉 {filtered} 条 / 跳过 {skipped} 条")
        total_added += added
        total_filtered += filtered
        total_skipped += skipped

    conn.close()
    print(
        f"总计：新增 {total_added} 条，过滤掉 {total_filtered} 条，跳过 {total_skipped} 条"
    )


if __name__ == "__main__":
    main()
