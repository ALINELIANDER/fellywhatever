"""Step 1 — Extract TODAY'S lesson text from the Hindi textbook PDF.

Usage (from backend/):
    python lesson_dictionary/process_lesson.py textbook.pdf \\
        --start-page 12 --end-page 15 --lesson-id lesson_01

Writes lessons/<lesson_id>/source_text.txt and vocabulary.json.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db
import vocabulary as vocab
import _console
from app.services.pdf_extractor import PdfExtractor
from config import LESSONS_DIR


def extract_lesson_text(pdf_path, start_page, end_page):
    extractor = PdfExtractor(pdf_path)
    try:
        pages = extractor.extract_range(start_page, end_page)
    finally:
        extractor.close()
    return "\n\n".join(p["text"] for p in pages if p["text"]).strip()


def run_extraction(pdf_path, start_page, end_page, lesson_id,
                   lesson_title="", max_words=50):
    """Extract today's lesson text + vocabulary and persist to lessons/<lesson_id>.

    Returns the payload dict that is also written to vocabulary.json.
    """
    db.init_db()
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    text = extract_lesson_text(str(pdf), start_page, end_page)
    if not text:
        raise ValueError("No text extracted from the selected pages.")

    return run_extraction_from_text(
        text, lesson_id, lesson_title, max_words,
        pdf_path=str(pdf), start_page=start_page, end_page=end_page,
    )


def run_extraction_from_text(text, lesson_id, lesson_title="", max_words=50,
                             pdf_path="", start_page=0, end_page=0):
    """Persist vocabulary from already-extracted lesson text.

    Content Library has already extracted the selected pages, so callers can
    share that exact text instead of reading the PDF again.
    """
    db.init_db()
    text = (text or "").strip()
    if not text:
        raise ValueError("No text extracted from the selected pages.")

    items = vocab.extract_vocabulary(text, max_words=max_words)

    lesson_dir = LESSONS_DIR / lesson_id
    lesson_dir.mkdir(parents=True, exist_ok=True)
    (lesson_dir / "source_text.txt").write_text(text, encoding="utf-8")
    payload = {
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "pdf_path": pdf_path,
        "start_page": start_page,
        "end_page": end_page,
        "word_count": len(items),
        "words": items,
    }
    (lesson_dir / "vocabulary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser(description="Extract today's lesson from a Hindi textbook PDF.")
    parser.add_argument("pdf_path", help="Path to the Hindi textbook PDF")
    parser.add_argument("--start-page", type=int, required=True, help="First page (1-based)")
    parser.add_argument("--end-page", type=int, required=True, help="Last page (inclusive)")
    parser.add_argument("--lesson-id", required=True, help="e.g. lesson_01")
    parser.add_argument("--lesson-title", default="", help="Optional human-readable lesson title")
    parser.add_argument("--max-words", type=int, default=50, help="Cap on vocabulary size")
    args = parser.parse_args()

    payload = run_extraction(args.pdf_path, args.start_page, args.end_page,
                             args.lesson_id, args.lesson_title, args.max_words)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
