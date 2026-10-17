"""排序打分：final_score = interest_weight × heat_score × time_decay × source_quality - read_penalty。"""

import math
from datetime import datetime, timezone


def calc_final_score(item: dict, interest_weight: float, source_quality: float = 1.0) -> float:
    """
    item 需/可选字段：
      published_at  datetime（有则按发布时间衰减，无则按 24 小时计）
      heat_score    float 0-1（RSS 默认 0.5；HN 为 score/500，封顶 1.0）
      is_read / is_hidden / is_saved  bool（已读 -1.0 / 已隐藏 -5.0 / 已收藏 +2.0）

    time_decay = max(exp(-hours / 72), 0.1)：3 天衰减到 0.37；任何内容保底 0.1，不会归零。
    """
    published_at = item.get("published_at")
    if published_at:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
    else:
        hours = 24.0
    hours = max(hours, 0.0)  # 防止未来时间导致衰减大于 1

    time_decay = max(math.exp(-hours / 72), 0.1)

    heat_score = item.get("heat_score", 0.5)
    score = interest_weight * heat_score * time_decay * source_quality

    if item.get("is_read"):
        score -= 1.0
    if item.get("is_hidden"):
        score -= 5.0
    if item.get("is_saved"):
        score += 2.0

    return round(score, 4)


def get_source_quality(source_name: str, conn) -> float:
    """按用户反馈动态计算来源质量分。

    基础分 1.0；每个 like +0.1；每个 hide -0.2；最终夹在 [0.2, 2.0]。
    读的是 user_feedback 表（由 init_db 建好）。
    """
    if not source_name:
        return 1.0

    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN feedback_type = 'like' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN feedback_type = 'hide' THEN 1 ELSE 0 END), 0)
        FROM user_feedback
        WHERE source_name = ?
        """,
        (source_name,),
    ).fetchone()

    likes, hides = (row[0], row[1]) if row else (0, 0)
    quality = 1.0 + 0.1 * likes - 0.2 * hides
    return round(min(max(quality, 0.2), 2.0), 4)
