"""URL 归一化与去重哈希。"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# 需要剔除的追踪参数；另外 utm_* 前缀的也会一并剔除
TRACKING_PARAMS = {
    "ref",
    "from",
    "spm",
    "source",
    "share_token",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}


def normalize_url(url: str) -> str:
    """归一化 URL：

    1. 去掉 fragment（#...）
    2. 去掉 utm_* 等追踪参数（保留其余 query 顺序）
    3. 域名小写
    4. 去掉 path 尾部多余的斜杠
    """
    parsed = urlparse(url.strip())

    # 1. 去 fragment
    parsed = parsed._replace(fragment="")

    # 2. 去追踪参数
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]

    # 3. 域名小写   4. 去尾部斜杠（根路径统一为 "/"）
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    return urlunparse(
        (parsed.scheme, netloc, path, parsed.params, urlencode(query), "")
    )


def url_hash(url: str) -> str:
    """对归一化后的 URL 取 sha256 十六进制摘要。"""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
