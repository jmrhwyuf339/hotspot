"""文本翻译：优先 deep-translator 的 GoogleTranslator，失败时回退 MyMemoryTranslator。

- 任何异常都不中断程序；两个后端都失败时返回原文。
- Google 在本机被墙时，connect 超时会拖到 30s+（httpx/requests 会逐个地址重试），
  所以这里用「守护线程 + join(timeout)」做硬超时，保证单条最多等 TRANSLATE_TIMEOUT 秒。
- 一旦某次运行里 Google 判定不可达，本次运行就不再重复尝试（否则 60 条会白等半小时）。
"""

import threading

from deep_translator import GoogleTranslator, MyMemoryTranslator

# 单条翻译的最长等待（秒）
TRANSLATE_TIMEOUT = 6.0

# MyMemory 用配额耗尽/参数错误时会把提示当译文返回，需要当成失败
_MYMEMORY_BAD_PREFIXES = ("MYMEMORY WARNING", "PLEASE SELECT TWO DISTINCT", "QUERY LENGTH LIMIT")

# 本次进程内 Google 是否仍然可用（首次连不上后置 False）
_google_available = True


def _call_with_timeout(func, text: str, timeout: float) -> str:
    """在守护线程里执行 func(text)，超时抛 TimeoutError。"""
    box: dict = {}

    def runner() -> None:
        try:
            box["result"] = func(text)
        except Exception as e:  # noqa: BLE001
            box["error"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"translation timed out after {timeout}s")
    if "error" in box:
        raise box["error"]
    return box.get("result") or ""


def translate_text(text: str, target_lang: str = "zh-CN") -> str:
    """把 text 翻译成 target_lang；失败时返回原文本。"""
    global _google_available

    if not text or not text.strip():
        return text

    # 1) 首选 Google（符合规格；GitHub Actions 的海外网络可达）
    if _google_available:
        try:
            result = _call_with_timeout(
                GoogleTranslator(source="auto", target=target_lang).translate,
                text,
                TRANSLATE_TIMEOUT,
            )
            if result:
                return result
        except Exception as e:  # noqa: BLE001
            print(f"  [translate] Google 不可用（{type(e).__name__}），本次运行改用 MyMemory")
            _google_available = False

    # 2) 回退 MyMemory（免费、无需 key）
    try:
        result = _call_with_timeout(
            MyMemoryTranslator(source="en-US", target=target_lang).translate,
            text,
            TRANSLATE_TIMEOUT,
        )
        if result and not result.upper().startswith(_MYMEMORY_BAD_PREFIXES):
            return result
    except Exception as e:  # noqa: BLE001
        print(f"  [translate error] MyMemory 也失败：{type(e).__name__}: {e}")

    return text
