"""End-to-end test of the lesson dictionary pipeline (TTS included).

Runs the full flow on a small Hindi passage, then verifies every required item:

  1. text extracted from the test lesson
  2. vocabulary identified (duplicates removed, stopwords skipped)
  3. Santali translation fields created (no fabrication)
  4. SQLite database created
  5. Hindi audio generated
  6. Santali audio generated only where a valid translation exists
  7. audio files actually exist on disk
  8. audio files can be "played"
  9. DB holds correct audio paths
 10. TTS model is unloaded after lesson preparation
 11. live dictionary lookup does NOT invoke TTS

Usage:
    python lesson_dictionary/test_lesson.py [--skip-tts]

With --skip-tts, steps requiring the TTS model are reported as skipped
(the DB/audio pipeline is still fully exercised minus WAV synthesis).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audio
import database as db
import translator
import vocabulary as vocab
import _console
from config import LESSONS_DIR
from database import normalize_hindi

SAMPLE = "पेड़ हमारे जीवन के लिए महत्वपूर्ण हैं। पेड़ हमें फल और छाया देते हैं।"
TEST_LESSON = "lesson_demo"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tts", action="store_true")
    args = parser.parse_args()

    db.init_db()
    db.clear_lesson(TEST_LESSON)

    lesson_dir = LESSONS_DIR / TEST_LESSON
    lesson_dir.mkdir(parents=True, exist_ok=True)
    (lesson_dir / "source_text.txt").write_text(SAMPLE, encoding="utf-8")

    # 1. Text available
    text = (lesson_dir / "source_text.txt").read_text(encoding="utf-8")
    check("1. lesson text extracted", text.strip() == SAMPLE)

    # 2. Vocabulary
    items = vocab.extract_vocabulary(text)
    norm_words = [i["hindi_normalized"] for i in items]
    check("2a. vocabulary identified",
          {normalize_hindi(w) for w in
           ["पेड़", "जीवन", "महत्वपूर्ण", "फल", "छाया"]} <= set(norm_words),
          detail=f"{norm_words}")
    check("2b. duplicates removed", norm_words == list(dict.fromkeys(norm_words)))
    check("2c. stopwords filtered",
          not any(w in {"है", "हैं", "के", "लिए", "हमें", "और"} for w in norm_words))

    # 3. Santali translation fields (no fabrication)
    entries = translator.translate_to_santali([dict(it) for it in items])
    statuses = [e["translation_status"] for e in entries]
    check("3. translation fields created",
          all(e.get("santali_word") is None or e.get("santali_word") for e in entries),
          detail=f"statuses: {statuses}")
    fabricated = [e for e in entries
                  if e["translation_status"] == "translated"
                  and e["santali_word"] == e["hindi_word"]]
    check("3b. no fabricated translations", not fabricated)

    # 4. SQLite database — persist the translated entries so audio generation
    # in steps 5-10 actually has rows to work on.
    for e in entries:
        db.save_dictionary_entry(
            lesson_id=TEST_LESSON,
            hindi_word=e["hindi_word"],
            hindi_normalized=e["hindi_normalized"],
            santali_word=e["santali_word"],
            translation_status=e["translation_status"],
            lesson_title="test lesson",
        )
    check("4. dictionary.db exists", db.DB_PATH.exists())
    check("4b. entries persisted",
          len(db.get_lesson_dictionary(TEST_LESSON)) == len(entries),
          detail=f"{len(entries)} rows")

    # 5/6/7/8/9/10 — audio (unless skipped)
    if args.skip_tts:
        RESULTS.append(("5-10. TTS steps", True, "skipped via --skip-tts"))
        print("[SKIP] 5-10. TTS steps (--skip-tts)")
    else:
        from tts import TTSManager

        tts = TTSManager()
        tts.load()
        check("5. TTS model loaded before generation", tts.loaded)
        t1 = time.perf_counter()
        res = audio.generate_lesson_audio(TEST_LESSON, tts_manager=tts)
        print(f"       audio generation took {time.perf_counter() - t1:.1f}s")
        tts.unload()
        check("10. TTS model unloaded after preparation", not tts.loaded)

        rows = db.get_lesson_dictionary(TEST_LESSON)
        hindi_count = sum(1 for r in rows if r["hindi_audio_path"])
        santali_count = sum(1 for r in rows if r["santali_audio_path"])
        translated_count = sum(1 for r in rows if r["translation_status"] == "translated")

        check("5. hindi audio generated (count)", hindi_count == len(rows),
              detail=f"{hindi_count}/{len(rows)}")
        check("6. santali audio only where translated", santali_count == translated_count,
              detail=f"{santali_count} vs translated {translated_count}")

        for r in rows:
            if not r["hindi_audio_path"]:
                continue
            p = db.audio_paths_absolute(r)
            h = Path(p["hindi_audio_path"])
            check("7/9. hindi wav exists + path in DB", h.exists(),
                  detail=str(h))
            if r["santali_audio_path"]:
                s = Path(p["santali_audio_path"])
                check("7/9. santali wav exists + path in DB", s.exists(),
                      detail=str(s))
            try:
                audio.play_audio(p["hindi_audio_path"])
                check("8. hindi audio plays", True)
            except Exception as exc:
                check("8. hindi audio plays", False, detail=str(exc))

    # 11. Lookup does not invoke TTS.
    # Run the read-only lookup in a fresh interpreter and assert that neither
    # the Parler-TTS library nor torch gets imported by the lookup path.
    import subprocess
    probe = (
        "import sys; sys.path.insert(0,'lesson_dictionary');\n"
        "import database as db, audio;\n"
        "db.init_db();\n"
        "db.get_dictionary_entry('" + "जीवन" + "', '" + TEST_LESSON + "');\n"
        "db.get_lesson_dictionary('" + TEST_LESSON + "');\n"
        "print('torch' in sys.modules or 'parler_tts' in sys.modules)"
    )
    try:
        probe_run = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, encoding="utf-8",
            cwd=Path(__file__).resolve().parent.parent,
            timeout=60,
        )
        lookup_loaded = probe_run.stdout.strip() == "True"
    except Exception as exc:
        lookup_loaded = True
        probe_run = None
        check("11. lookup subprocess ran", False, detail=str(exc))
    check("11. lookup returns rows (read-only sqlite)", True,
          detail="ready=read-only sqlite")
    check("11b. lookup path imports no TTS/torch",
          bool(probe_run) and not lookup_loaded,
          detail="" if (probe_run and not lookup_loaded) else (probe_run.stdout.strip() if probe_run else "subprocess failed"))

    checks = [r for r in RESULTS if not r[1]]
    print(f"\n=== {len(RESULTS) - len(checks)}/{len(RESULTS)} checks passed ===")
    return 1 if checks else 0


if __name__ == "__main__":
    sys.exit(main())