"""Step 3 — Generate offline Hindi + Santali audio for one lesson.

Usage (from backend/):
    python lesson_dictionary/generate_audio.py --lesson-id lesson_01

Loads Indic Parler-TTS, synthesizes WAV files, unloads the model at the end.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audio
import database as db
import _console
from tts import TTSManager


def generate_lesson_audio(lesson_id, limit=None):
    tts = TTSManager()
    try:
        tts.load()
        result = audio.generate_lesson_audio(lesson_id, tts_manager=tts, limit=limit)
    finally:
        tts.unload()
    return result


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser(description="Generate offline TTS audio for a lesson.")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N entries (0 = all)")
    args = parser.parse_args()

    db.init_db()
    result = generate_lesson_audio(args.lesson_id, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("TTS model unloaded.")


if __name__ == "__main__":
    main()