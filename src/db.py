"""SQLite 数据库：连接与建表。

数据库文件 hotspot.db 固定放在项目根目录（与运行时的当前目录无关）。
"""

import sqlite3
from pathlib import Path

# src/db.py -> 上一级就是项目根目录
DB_PATH = Path(__file__).resolve().parents[1] / "hotspot.db"

# 用 CREATE TABLE IF NOT EXISTS，可重复运行
CREATE_ITEMS_SQL = """
CREATE TABLE IF NOT EXISTS items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    url_hash     TEXT NOT NULL UNIQUE,
    summary      TEXT,
    author       TEXT,
    published_at TIMESTAMP,
    fetched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    final_score  REAL DEFAULT 0,
    is_read      INTEGER DEFAULT 0,
    is_saved     INTEGER DEFAULT 0,
    is_hidden    INTEGER DEFAULT 0,
    interest     TEXT,
    source_name  TEXT
);
"""

CREATE_FEEDBACK_SQL = """
CREATE TABLE IF NOT EXISTS user_feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name   TEXT,
    feedback_type TEXT,               -- 'like' 或 'hide'
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn(db_path: "Path | str" = DB_PATH) -> sqlite3.Connection:
    """打开连接，返回 Row 工厂的连接。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """老库兼容：缺列就用 ALTER TABLE 补上。"""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
    for col in ("interest", "source_name"):
        if col not in existing:
            conn.execute(f"ALTER TABLE items ADD COLUMN {col} TEXT")


def init_db(db_path: "Path | str" = DB_PATH) -> sqlite3.Connection:
    """建表（幂等）+ 补列（兼容阶段二的旧库），返回已就绪的连接。"""
    conn = get_conn(db_path)
    conn.execute(CREATE_ITEMS_SQL)
    conn.execute(CREATE_FEEDBACK_SQL)
    _ensure_columns(conn)
    conn.commit()
    return conn


def add_feedback(
    source_name: str,
    feedback_type: str,
    conn: "sqlite3.Connection | None" = None,
) -> None:
    """记录一次来源反馈（feedback_type：'like' 或 'hide'）。

    不传 conn 时自己开关连接并立即提交；传入 conn 时复用该连接，
    由调用方统一 commit —— 避免同一进程内两个连接互相把库锁死。
    """
    own = conn is None
    if own:
        conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO user_feedback (source_name, feedback_type) VALUES (?, ?)",
            (source_name, feedback_type),
        )
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()
