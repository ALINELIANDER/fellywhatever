import re
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.services import pdf_extractor

router = APIRouter(tags=["dictionary"])

_LD_DIR = Path(__file__).resolve().parent.parent.parent / "lesson_dictionary"
if str(_LD_DIR) not in sys.path:
    sys.path.insert(0, str(_LD_DIR))

# Make backend/ importable too (for app.services.pdf_extractor).
_BACKEND_DIR = _LD_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import config as ld_config  # noqa: E402
import database as ld_db  # noqa: E402
import process_lesson  # noqa: E402
import build_dictionary  # noqa: E402
import audio  # noqa: E402

_AUDIO_DIR = ld_config.AUDIO_DIR
_LANG_ALLOW = {"hindi", "santali"}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class GenerateRequest(BaseModel):
    textbook_id: str = ""
    source: str = ""
    from_page: int = 2
    to_page: int = 3
    lesson_id: str = ""
    lesson_title: str = ""
    max_words: int = 50
    generate_audio: bool = False


class AudioRequest(BaseModel):
    lesson_id: str
    limit: int = 0


@router.get("/dictionary/lessons")
def dictionary_lessons():
    ld_db.init_db()
    conn = ld_db.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT lesson_id, lesson_title, COUNT(*) AS entry_count,
                   SUM(CASE WHEN santali_word IS NOT NULL THEN 1 ELSE 0 END) AS translated_count,
                   SUM(CASE WHEN hindi_audio_path IS NOT NULL THEN 1 ELSE 0 END) AS with_audio
            FROM dictionary_entries
            GROUP BY lesson_id, lesson_title
            ORDER BY lesson_id
            """
        ).fetchall()
    finally:
        conn.close()
    return {
        "success": True,
        "lessons": [
            {
                "lesson_id": r["lesson_id"],
                "lesson_title": r["lesson_title"],
                "entry_count": r["entry_count"],
                "translated_count": r["translated_count"] or 0,
                "with_audio": r["with_audio"] or 0,
            }
            for r in rows
        ],
    }


@router.get("/dictionary/{lesson_id}")
def dictionary_lesson(lesson_id: str):
    if not _ID_RE.fullmatch(lesson_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid lesson id."}
        )
    return _shared_rows(lesson_id)


@router.get("/dictionary/{lesson_id}/audio/{lang}/{filename}")
def dictionary_audio(lesson_id: str, lang: str, filename: str):
    if lang not in _LANG_ALLOW or not _ID_RE.fullmatch(lesson_id) or \
            not _FILENAME_RE.fullmatch(filename):
        return JSONResponse(
            status_code=404, content={"success": False, "error": "Not found."}
        )
    wav = (_AUDIO_DIR / lesson_id / lang / filename).resolve()
    if not wav.is_file() or _AUDIO_DIR.resolve() not in wav.parents:
        return JSONResponse(
            status_code=404, content={"success": False, "error": "Audio not found."}
        )
    return FileResponse(wav, media_type="audio/wav")


def _shared_rows(lesson_id):
    rows = ld_db.get_lesson_dictionary(lesson_id)
    entries = []
    for r in rows:
        abs_paths = ld_db.audio_paths_absolute(r)
        entries.append(
            {
                "id": r["id"],
                "lesson_id": r["lesson_id"],
                "hindi_word": r["hindi_word"],
                "hindi_normalized": r["hindi_normalized"],
                "santali_word": r["santali_word"],
                "translation_status": r["translation_status"],
                "example_hindi": r["example_hindi"],
                "example_santali": r["example_santali"],
                "hindi_audio_url": (
                    f"/dictionary/{lesson_id}/audio/hindi/{Path(r['hindi_audio_path']).name}"
                    if r["hindi_audio_path"] else None
                ),
                "santali_audio_url": (
                    f"/dictionary/{lesson_id}/audio/santali/{Path(r['santali_audio_path']).name}"
                    if r["santali_audio_path"] else None
                ),
            }
        )
    return {"success": True, "lesson_id": lesson_id, "entries": entries}


@router.post("/dictionary/generate")
def generate_dictionary(req: GenerateRequest):
    if req.from_page < 1 or req.to_page < req.from_page or req.max_words < 1:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid page range or max_words."},
        )

    # Source: either an uploaded textbook (Content Library) or a backend-relative
    # PDF path. No pre-stored books are referenced here.
    pdf = None
    if req.textbook_id:
        if not _ID_RE.fullmatch(req.textbook_id):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid textbook id."},
            )
        pdf = _BACKEND_DIR / "uploads" / f"{req.textbook_id}.pdf"
        if not pdf.is_file():
            return JSONResponse(
                status_code=400,
                content={"success": False,
                         "error": "Uploaded textbook not found — upload it in Content Library first."},
            )
    elif req.source:
        pdf = Path(req.source)
        if not pdf.is_absolute():
            pdf = _BACKEND_DIR / pdf
        if not pdf.is_file():
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Textbook PDF not found: {req.source}"},
            )
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False,
                     "error": "No textbook given. Upload it in Content Library first."},
        )

    # Auto-assign a lesson id when the teacher just pressed "Generate".
    lesson_id = req.lesson_id
    if not lesson_id:
        conn = ld_db.get_connection()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT lesson_id FROM dictionary_entries")]
        finally:
            conn.close()
        n = len(ids) + 1
        lesson_id = f"lesson_{n:02d}"
        while lesson_id in ids:
            n += 1
            lesson_id = f"lesson_{n:02d}"
    elif not _ID_RE.fullmatch(lesson_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid lesson id."}
        )
    lesson_title = req.lesson_title or Path(pdf).stem

    try:
        extracted = pdf_extractor.load_cached_lesson(
            req.textbook_id, req.from_page, req.to_page
        ) if req.textbook_id else None
        if extracted and extracted.get("combined_text"):
            payload = process_lesson.run_extraction_from_text(
                extracted["combined_text"], lesson_id, lesson_title, req.max_words,
                pdf_path=str(pdf), start_page=req.from_page, end_page=req.to_page,
            )
        else:
            payload = process_lesson.run_extraction(
                str(pdf), req.from_page, req.to_page,
                lesson_id, lesson_title, req.max_words,
            )
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )

    ld_db.clear_lesson(lesson_id)
    try:
        entries = build_dictionary.build_dictionary(lesson_id, lesson_title)
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )

    translated = sum(1 for e in entries if e["translation_status"] == "translated")
    result = {
        "success": True,
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "word_count": payload["word_count"],
        "entries_count": len(entries),
        "translated_count": translated,
        "message": f"Dictionary generated: {len(entries)} words "
                   f"({translated} translated).",
        "entries": _shared_rows(lesson_id)["entries"],
    }
    if req.generate_audio:
        try:
            from tts import TTSManager

            tts = TTSManager()
            tts.load()
            result["audio"] = audio.generate_lesson_audio(lesson_id, tts_manager=tts)
        except Exception as exc:
            return JSONResponse(
                status_code=500, content={"success": False, "error": str(exc)}
            )
        finally:
            if 'tts' in locals():
                tts.unload()
        result["entries"] = _shared_rows(lesson_id)["entries"]
    return result


@router.post("/dictionary/generate-audio")
def generate_audio(req: AudioRequest):
    if not _ID_RE.fullmatch(req.lesson_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid lesson id."}
        )
    if req.limit < 0:
        return JSONResponse(
            status_code=400, content={"success": False, "error": "limit must be >= 0."}
        )
    existing = ld_db.get_lesson_dictionary(req.lesson_id)
    if not existing:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Lesson '{req.lesson_id}' has no entries."}
        )

    from tts import TTSManager

    tts = None
    try:
        tts = TTSManager()
        tts.load()
        result = audio.generate_lesson_audio(req.lesson_id, tts_manager=tts,
                                             limit=req.limit if req.limit else None)
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(exc)}
        )
    finally:
        if tts is not None:
            tts.unload()

    result["success"] = True
    result["lesson_id"] = req.lesson_id
    return result
