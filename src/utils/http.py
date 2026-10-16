"""HTTP 抓取工具：带浏览器 User-Agent、15 秒超时、简单重试。"""

import time
from typing import Optional

import httpx

# 使用真实浏览器 UA，避免被当作脚本直接拒绝
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

TIMEOUT = 15.0  # 单请求 15 秒超时


def fetch(url: str, retries: int = 3) -> Optional[str]:
    """GET 请求，返回响应文本。

    - 浏览器 User-Agent
    - 单请求 15 秒超时
    - 失败重试 retries 次（指数退避 1s / 2s / 4s），全部失败返回 None
    """
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers=HEADERS)
                if resp.status_code == 200:
                    return resp.text
                print(
                    f"[fetch] {url} -> HTTP {resp.status_code} "
                    f"(attempt {attempt + 1}/{retries})"
                )
                time.sleep(2 ** attempt)
        except Exception as e:  # noqa: BLE001 - 单源失败不应抛出中断
            print(f"[fetch error] {url} attempt {attempt + 1}/{retries}: {e}")
            time.sleep(2 ** attempt)
    return None
