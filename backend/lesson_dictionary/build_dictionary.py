"""Step 2 — Write dictionary entries + Santali translations to SQLite.

Usage (from backend/):
    python lesson_dictionary/build_dictionary.py --lesson-id lesson_01
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db
import translator
import _console
from config import LESSONS_DIR


def build_dictionary(lesson_id, lesson_title="", use_translator=True):
    db.init_db()
    vocab_path = LESSONS_DIR / lesson_id / "vocabulary.json"
    if not vocab_path.exists():
        sys.exit(f"Run process_lesson.py first — missing {vocab_path}")

    payload = json.loads(vocab_path.read_text(encoding="utf-8"))
    items = payload["words"]
    lesson_title = lesson_title or payload.get("lesson_title", "")

    entries = []
    for it in items:
        entry = dict(it)
        entry["lesson_id"] = lesson_id
        entry["lesson_title"] = lesson_title
        entry["example_hindi"] = ""
        entry["example_santali"] = ""
        entry["santali_word"] = None
        entry["translation_status"] = "pending"
        entries.append(entry)

    if use_translator:
        entries = translator.translate_to_santali(entries)

    for e in entries:
        db.save_dictionary_entry(
            lesson_id=e["lesson_id"],
            hindi_word=e["hindi_word"],
            hindi_normalized=e["hindi_normalized"],
            santali_word=e["santali_word"],
            translation_status=e["translation_status"],
            lesson_title=lesson_title,
            example_hindi=e["example_hindi"],
            example_santali=e["example_santali"],
        )
    return entries


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser(description="Build dictionary entries for a lesson.")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--lesson-title", default="")
    parser.add_argument("--no-translate", action="store_true",
                        help="Skip Santali translation (all entries stay pending/unavailable)")
    args = parser.parse_args()

    entries = build_dictionary(args.lesson_id, args.lesson_title,
                               use_translator=not args.no_translate)

    translated = sum(1 for e in entries if e["translation_status"] == "translated")
    print(json.dumps({
        "lesson_id": args.lesson_id,
        "entries": len(entries),
        "translated": translated,
        "unavailable": len(entries) - translated,
        "records": entries,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()