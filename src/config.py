"""加载 config/ 下的兴趣与数据源 YAML。"""

from pathlib import Path
from typing import Optional

import yaml

# src/config.py -> 上一级是项目根目录
CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
INTERESTS_FILE = CONFIG_DIR / "interests.yaml"
SOURCES_FILE = CONFIG_DIR / "sources.yaml"


def _load_yaml(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_interests(path=None) -> list[dict]:
    """返回 interests.yaml 里的 interests 列表。"""
    data = _load_yaml(path or INTERESTS_FILE)
    return data.get("interests", []) or []


def load_sources(path=None) -> list[dict]:
    """返回 sources.yaml 里的 sources 列表。"""
    data = _load_yaml(path or SOURCES_FILE)
    return data.get("sources", []) or []


def get_interest(interests: list[dict], name: str) -> Optional[dict]:
    """按兴趣名查找。"""
    return next((i for i in interests if i.get("name") == name), None)
