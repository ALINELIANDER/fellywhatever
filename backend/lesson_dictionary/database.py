import re
import sqlite3
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS dictionary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    lesson_title TEXT,
    hindi_word TEXT NOT NULL,
    hindi_normalized TEXT NOT NULL,
    santali_word TEXT,
    translation_status TEXT NOT NULL DEFAULT 'pending',
    example_hindi TEXT,
    example_santali TEXT,
    image_path TEXT,
    hindi_audio_path TEXT,
    santali_audio_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lesson_id ON dictionary_entries(lesson_id);
CREATE INDEX IF NOT EXISTS idx_hindi_normalized ON dictionary_entries(hindi_normalized);
"""

NORMALIZE_RE = re.compile(r"[\u0900-\u0903\u093c\u094d\u200c\u200d]")


def normalize_hindi(word):
    word = word.strip()
    word = re.sub(r"[़्]|\u200c|\u200d", "", word)
    word = word.replace("ँ", "").replace("ं", "").replace("ः", "")
    return word


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


def save_dictionary_entry(
    lesson_id,
    hindi_word,
    hindi_normalized,
    santali_word,
    translation_status,
    lesson_title="",
    example_hindi="",
    example_santali="",
    image_path=None,
    hindi_audio_path=None,
    santali_audio_path=None,
):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO dictionary_entries (
                lesson_id, lesson_title, hindi_word, hindi_normalized,
                santali_word, translation_status, example_hindi, example_santali,
                image_path, hindi_audio_path, santali_audio_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson_id,
                lesson_title,
                hindi_word,
                hindi_normalized,
                santali_word,
                translation_status,
                example_hindi,
                example_santali,
                image_path,
                hindi_audio_path,
                santali_audio_path,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_lesson_dictionary(lesson_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM dictionary_entries WHERE lesson_id = ? ORDER BY id",
            (lesson_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_dictionary_entry(hindi_normalized, lesson_id):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM dictionary_entries
            WHERE hindi_normalized = ? AND lesson_id = ?
            """,
            (hindi_normalized, lesson_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_audio_paths(entry_id, hindi_audio_path, santali_audio_path):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE dictionary_entries
            SET hindi_audio_path = ?, santali_audio_path = ?
            WHERE id = ?
            """,
            (hindi_audio_path, santali_audio_path, entry_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_translation(entry_id, santali_word, translation_status):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE dictionary_entries
            SET santali_word = ?, translation_status = ?
            WHERE id = ?
            """,
            (santali_word, translation_status, entry_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_entries():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM dictionary_entries").fetchone()["n"]
    finally:
        conn.close()


def clear_lesson(lesson_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM dictionary_entries WHERE lesson_id = ?", (lesson_id,))
        conn.commit()
    finally:
        conn.close()


def audio_paths_absolute(row):
    out = dict(row)
    for key in ("hindi_audio_path", "santali_audio_path"):
        if out.get(key):
            p = Path(out[key])
            if not p.is_absolute():
                p = DB_PATH.parent / p
            out[key] = str(p.resolve())
    return out