"""兴趣匹配：按关键词命中、排除词过滤。

中文关键词沿用「包含即命中」；纯 ASCII（英文）关键词用 \\b 词边界匹配，
避免 "Main" 命中 "AI"、"Freeform" 命中 "free" 这类子串误报。

另有一条「信源即态度」通路：sources.yaml 里标了 trusted: true 的源，
其条目不要求命中 keywords（依据是源本身的调性），只受 exclude 兜底。
"""

import re


def _ascii_pattern(keyword: str) -> "re.Pattern[str]":
    # 词边界匹配，不区分大小写
    return re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)


def _hit(text: str, keyword: str) -> bool:
    """text 需为小写文本。ASCII 关键词按词边界匹配，其余按包含匹配。"""
    if keyword.isascii():
        return _ascii_pattern(keyword).search(text) is not None
    return keyword.lower() in text


def match_interest(item: dict, interest: dict, trusted: bool = False) -> bool:
    """是否算这个兴趣的条目。

    trusted=True（条目来自 trusted 源）：免关键词命中，但仍必须不含任何 exclude。
    否则：标题或 summary 命中任一 keyword，且不含任何 exclude，才返回 True。
    """
    keywords = interest.get("keywords") or []
    excludes = interest.get("exclude") or []

    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

    # 排除词永远优先：trusted 只是免掉「必须命中」，不是免掉「不许出现」
    if any(_hit(text, ex) for ex in excludes):
        return False
    if trusted:
        return True
    return any(_hit(text, kw) for kw in keywords)
