"""Step 4 — View / search the dictionary (read-only, NO TTS).

Usage (from backend/):
    python lesson_dictionary/dictionary_lookup.py --lesson-id lesson_01
    python lesson_dictionary/dictionary_lookup.py --lesson-id lesson_01 --search पेड़
    python lesson_dictionary/dictionary_lookup.py --lesson-id lesson_01 --play 3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audio
import database as db
import _console


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser(description="Look up lesson dictionary entries.")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--search", default="", help="Search Hindi or Santali word (substring)")
    parser.add_argument("--play", type=int, default=0, help="Entry row number to play audio for")
    parser.add_argument("--lang", choices=["hindi", "santali", "both"], default="both")
    args = parser.parse_args()

    db.init_db()
    entries = db.get_lesson_dictionary(args.lesson_id)
    if not entries:
        sys.exit(f"No entries found for lesson '{args.lesson_id}'.")

    if args.search:
        q = args.search.strip()
        entries = [e for e in entries
                   if q in e["hindi_word"] or q in e["hindi_normalized"]
                   or q in (e["santali_word"] or "")]

    if args.play:
        e = entries[args.play - 1]
        e = db.audio_paths_absolute(e)
        paths = []
        if args.lang in ("hindi", "both") and e.get("hindi_audio_path"):
            paths.append(e["hindi_audio_path"])
        if args.lang in ("santali", "both") and e.get("santali_audio_path"):
            paths.append(e["santali_audio_path"])
        for p in paths:
            print(f"Playing {p}")
            audio.play_audio(p)
        return

    for n, e in enumerate(entries, start=1):
        e = db.audio_paths_absolute(e)
        print(f"[{n}] {e['hindi_word']}  (norm: {e['hindi_normalized']})")
        print(f"    santali: {e['santali_word'] or '—'}  status: {e['translation_status']}")
        print(f"    hindi  audio: {e.get('hindi_audio_path')}")
        print(f"    santali audio: {e.get('santali_audio_path')}")


if __name__ == "__main__":
    main()