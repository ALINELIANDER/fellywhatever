"""SQLite persistence for the Content Library "Visual aids for today" feature.

Reuses the exact SQLite database already used by the Dictionary feature
(``lesson_dictionary/dictionary.db``) and the same connection approach
(WAL, ``sqlite3.Row``), so there is no second database system. The new
``visual_aids`` table is additive and leaves the dictionary tables untouched.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_LD_DIR = Path(__file__).resolve().parent.parent.parent / "lesson_dictionary"
if str(_LD_DIR) not in sys.path:
    sys.path.insert(0, str(_LD_DIR))

from config import DB_PATH  # noqa: E402  (lesson_dictionary.config -> dictionary.db)

SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_aids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    label TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_visual_aids_lesson ON visual_aids(lesson_id);
"""


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_visual_aid(lesson_id, label, file_name, file_path, mime_type):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO visual_aids (lesson_id, label, file_name, file_path, mime_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lesson_id, label, file_name, file_path, mime_type),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM visual_aids WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_visual_aids(lesson_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM visual_aids WHERE lesson_id = ? ORDER BY id",
            (lesson_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_visual_aid(aid_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM visual_aids WHERE id = ?", (aid_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM visual_aids WHERE id = ?", (aid_id,))
        conn.commit()
        return dict(row)
    finally:
        conn.close()