"""排序打分：final_score = interest_weight × heat_score × time_decay × source_quality - read_penalty。

trusted 源（sources.yaml 里 trusted: true 的深度源）额外乘 TRUSTED_BOOST，并且用更慢的
时间衰减：这些源周更甚至月更，按日更快讯的曲线会被压到保底分，好文章立刻沉底。
"""

import math
from datetime import datetime, timezone

# trusted 源加成：深度长文产出少，先补一个系数
TRUSTED_BOOST = 1.5

# 时间衰减的时间常数（exp(-hours / TAU)）：常规源 3 天，trusted 源 7 天。
# 7 天常数下，一周前的深度文章还有 0.37 的衰减系数（3 天常数下只剩 0.1 保底）。
TAU_HOURS = 72.0
TRUSTED_TAU_HOURS = 168.0

# 衰减保底：任何内容都不会归零
TIME_DECAY_FLOOR = 0.1


def calc_final_score(
    item: dict,
    interest_weight: float,
    source_quality: float = 1.0,
    trusted: bool = False,
) -> float:
    """
    item 需/可选字段：
      published_at  datetime（有则按发布时间衰减，无则按 24 小时计）
      heat_score    float 0-1（RSS 默认 0.5；HN 为 score/500，封顶 1.0）
      is_read / is_hidden / is_saved  bool（已读 -1.0 / 已隐藏 -5.0 / 已收藏 +2.0）

    time_decay = max(exp(-hours / TAU), 0.1)：常规源 TAU=72h（3 天衰减到 0.37），
    trusted 源 TAU=168h（一周才衰减到 0.37）。任何内容保底 0.1，不会归零。
    trusted=True 时内容分先 × TRUSTED_BOOST，再加/减下面的已读隐藏收藏项
    （惩罚保持绝对值，不随加成放大）。
    """
    published_at = item.get("published_at")
    if published_at:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
    else:
        hours = 24.0
    hours = max(hours, 0.0)  # 防止未来时间导致衰减大于 1

    tau = TRUSTED_TAU_HOURS if trusted else TAU_HOURS
    time_decay = max(math.exp(-hours / tau), TIME_DECAY_FLOOR)

    heat_score = item.get("heat_score", 0.5)
    score = interest_weight * heat_score * time_decay * source_quality
    if trusted:
        score *= TRUSTED_BOOST

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
