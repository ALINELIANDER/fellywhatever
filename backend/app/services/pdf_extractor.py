import json
import re
from pathlib import Path

import fitz

from app.config import EXTRACTED_DIR, MAX_CACHED_LESSONS

_WS = re.compile(r"[ \t\u00a0\u2007\u2009\u200a\u202f\u3000]+")
_PAGE_NUMBER_ONLY = re.compile(r"^\d{1,4}$")
_BULLET = re.compile(r"^[•·‣◦▪*\-–—]")
_NUMBERED = re.compile(r"^\d+[.)।]")
_LETTERED = re.compile(r"^[a-zA-Z][.)]")
_DEVANA_LETTERED = re.compile(r"^[क-ह][.)।]")
_SENTENCE_END = ("।", "॥", ".", "?", "!", ":", ";")


def clean_text(raw):
    if not raw or not raw.strip():
        return ""
    text = raw.replace("\x0c", "\n")
    lines = []
    for ln in text.splitlines():
        ln = _WS.sub(" ", ln).strip()
        if ln and not _PAGE_NUMBER_ONLY.match(ln) and ln not in ("।", "॥"):
            lines.append(ln)
    blocks = []
    for i, ln in enumerate(lines):
        if not blocks:
            blocks.append(ln)
        elif _is_heading(ln) or _is_list_line(ln):
            blocks.append(ln)
        elif lines[i - 1].endswith(_SENTENCE_END) or _is_heading(lines[i - 1]) or _is_list_line(lines[i - 1]):
            blocks.append(ln)
        else:
            blocks[-1] = blocks[-1] + " " + ln
    return "\n\n".join(blocks).strip()


def _is_list_line(line):
    return bool(
        _BULLET.match(line)
        or _NUMBERED.match(line)
        or _LETTERED.match(line)
        or _DEVANA_LETTERED.match(line)
    )


def _is_heading(line):
    return not _is_list_line(line) and len(line) <= 30 and not line.endswith(_SENTENCE_END)


class PdfExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = Path(pdf_path)
        self.doc = None

    def open(self):
        if self.doc is None or self.doc.is_closed:
            self.doc = fitz.open(str(self.pdf_path))
        return self.doc

    def close(self):
        if self.doc is not None and not self.doc.is_closed:
            self.doc.close()
        self.doc = None

    @property
    def page_count(self):
        return self.open().page_count

    def extract_range(self, from_page, to_page):
        pages = []
        for idx in range(from_page - 1, to_page):
            raw, status = self._extract_page_text(idx)
            clean = clean_text(raw)
            if clean and status == "ok":
                status = "ok"
            elif not clean:
                status = "no_extractable_text"
            pages.append({"page_number": idx + 1, "text": clean, "status": status})
        return pages

    def _extract_page_text(self, page_index):
        doc = self.open()
        page = doc.load_page(page_index)
        try:
            raw = page.get_text("text")
            return raw, "ok"
        except Exception:
            return "", "extraction_error"


def build_lessons_map(textbook_id, from_page, to_page):
    lesson_text = EXTRACTED_DIR / textbook_id / f"pages_{from_page}_{to_page}.json"
    lesson_text.parent.mkdir(parents=True, exist_ok=True)
    return lesson_text


def get_or_extract_lesson(pdf_path, textbook_id, from_page, to_page, filename, total_pages):
    """Return the lesson payload for (textbook, page range).

    Serves from disk cache when available, otherwise extracts the requested
    pages with PyMuPDF (one page at a time) and caches the result. This is the
    single shared entry point used by both the extract endpoint and the
    learning-material generator, so PDF extraction is never duplicated.
    """
    cached = load_cached_lesson(textbook_id, from_page, to_page)
    if cached is not None:
        cached["cached"] = True
        return cached

    extractor = PdfExtractor(pdf_path)
    try:
        pages = extractor.extract_range(from_page, to_page)
    finally:
        extractor.close()

    combined_text = "\n\n".join(p["text"] for p in pages if p["text"])
    payload = {
        "success": True,
        "textbook_id": textbook_id,
        "filename": filename,
        "from_page": from_page,
        "to_page": to_page,
        "total_pages": total_pages,
        "pages": pages,
        "combined_text": combined_text,
        "cached": False,
    }
    save_cached_lesson(textbook_id, from_page, to_page, payload)
    return payload


def load_cached_lesson(textbook_id, from_page, to_page):
    path = build_lessons_map(textbook_id, from_page, to_page)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cached_lesson(textbook_id, from_page, to_page, payload):
    path = build_lessons_map(textbook_id, from_page, to_page)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _prune_old_lessons(path.parent)


def _prune_old_lessons(lesson_dir):
    files = sorted(lesson_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in files[:-MAX_CACHED_LESSONS]:
        try:
            old.unlink()
        except OSError:
            pass