import json
import time
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import (
    GENERATED_DIR,
    MAX_CACHED_MATERIAL,
    TRANSLATION_ENABLED,
    TRANSLATION_MODEL_NAME,
    TRANSLATION_REQUIRED,
    TRANSLATION_SOURCE_LANG,
    TRANSLATION_TARGET_LANG,
    UPLOAD_DIR,
)
from app.services import pdf_extractor, qwen_generator, translation_service

router = APIRouter(tags=["learning-material"])


class GenerateRequest(BaseModel):
    textbook_id: str
    from_page: int = 1
    to_page: int = 5
    high_quality: bool = False
    mcq_count: Optional[int] = None
    fitb_count: Optional[int] = None
    tf_count: Optional[int] = None


def _material_path(textbook_id, from_page, to_page, high_quality=False, quotas=None):
    folder = GENERATED_DIR / textbook_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"pages_{from_page}_{to_page}"
    if high_quality:
        name += "_hq"
    if quotas:
        name += "_c{}-{}-{}".format(
            quotas.get("mcqs", ""),
            quotas.get("fill_in_the_blanks", ""),
            quotas.get("true_false", ""),
        )
    return folder / f"{name}.json"


@router.get("/learning-material/{textbook_id}/{from_page}/{to_page}")
def get_learning_material(textbook_id: str, from_page: int, to_page: int):
    """Return the persisted material for one extracted lesson without generating it."""
    cache_path = _material_path(textbook_id, from_page, to_page)
    if not cache_path.exists():
        return _error(404, "No generated material exists for this lesson yet.")
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _error(500, "Generated lesson material is corrupted.")
    cached["cached"] = True
    return cached


def _prune_generated(lesson_dir):
    files = sorted(lesson_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for old in files[:-MAX_CACHED_MATERIAL]:
        try:
            old.unlink()
        except OSError:
            pass


def _load_lesson_or_error(textbook_id, from_page, to_page):
    meta_path = UPLOAD_DIR / f"{textbook_id}.json"
    pdf_path = UPLOAD_DIR / f"{textbook_id}.pdf"
    if not pdf_path.exists() or not meta_path.exists():
        return None, _error(404, f"Textbook '{textbook_id}' is not found. Upload it first.")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        total_pages = int(meta["total_pages"])
    except (json.JSONDecodeError, KeyError, OSError, ValueError):
        return None, _error(500, "Textbook metadata is missing or corrupted.")

    if from_page < 1:
        return None, _error(400, "from_page must be at least 1.")
    if to_page < from_page:
        return None, _error(400, "to_page cannot be smaller than from_page.")
    if to_page > total_pages:
        return None, _error(
            400,
            f"Page range exceeds textbook length. Textbook contains {total_pages} pages.",
        )

    payload = pdf_extractor.get_or_extract_lesson(
        pdf_path,
        textbook_id,
        from_page,
        to_page,
        meta.get("filename", ""),
        total_pages,
    )
    return payload, None


@router.post("/generate-learning-material")
def generate_learning_material(req: GenerateRequest):
    payload, err = _load_lesson_or_error(req.textbook_id, req.from_page, req.to_page)
    if err is not None:
        return err

    combined_text = (payload.get("combined_text") or "").strip()
    if not combined_text:
        return _error(
            422,
            "No extractable text in the selected pages. Choose a different page range.",
        )

    quotas = {}
    for field, name in (
        (req.mcq_count, "mcqs"),
        (req.fitb_count, "fill_in_the_blanks"),
        (req.tf_count, "true_false"),
    ):
        if field is not None:
            if field < 0:
                return _error(400, "Question counts must be zero or more.")
            quotas[name] = field

    cache_path = _material_path(
        req.textbook_id, req.from_page, req.to_page, req.high_quality, quotas or None
    )
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            stale_until_translated = TRANSLATION_ENABLED and not cached.get("bilingual")
            if not stale_until_translated:
                cached["cached"] = True
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    t_start = time.perf_counter()
    try:
        material, timing = qwen_generator.generate_learning_material(
            combined_text, high_quality=req.high_quality, quotas=quotas or None
        )
    except qwen_generator.ModelUnavailable as exc:
        return _error(503, str(exc))
    except qwen_generator.GenerationError as exc:
        return _error(422, str(exc))
    except MemoryError:
        return _error(
            500,
            "Not enough memory to run the model for this request. Close other "
            "applications and try again.",
        )
    except Exception as exc:
        return _error(500, f"Qwen generation failed: {exc}")

    bilingual = False
    if TRANSLATION_ENABLED:
        try:
            material = translation_service.bilingualize(material)
            bilingual = True
        except translation_service.TranslationError as exc:
            if TRANSLATION_REQUIRED:
                return _error(503, f"Hindi-Santali translation unavailable: {exc}")
            material.pop("bilingual", None)

    total_s = round(time.perf_counter() - t_start, 2)
    result = {
        "success": True,
        "textbook_id": req.textbook_id,
        "filename": payload.get("filename", ""),
        "from_page": req.from_page,
        "to_page": req.to_page,
        "worksheet": material["worksheet"],
        "flashcards": material["flashcards"],
        "bilingual": bilingual,
        "cached": False,
        "timing": {**timing, "total_s": total_s},
    }
    if bilingual:
        result["translation"] = {
            "source": TRANSLATION_SOURCE_LANG,
            "target": TRANSLATION_TARGET_LANG,
            "model": TRANSLATION_MODEL_NAME,
        }

    cacheable = {
        "success": True,
        "textbook_id": req.textbook_id,
        "filename": payload.get("filename", ""),
        "from_page": req.from_page,
        "to_page": req.to_page,
        "worksheet": material["worksheet"],
        "flashcards": material["flashcards"],
        "bilingual": bilingual,
        "cached": False,
    }
    if bilingual:
        cacheable["translation"] = {
            "source": TRANSLATION_SOURCE_LANG,
            "target": TRANSLATION_TARGET_LANG,
            "model": TRANSLATION_MODEL_NAME,
        }
    cache_path.write_text(
        json.dumps(cacheable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _prune_generated(cache_path.parent)

    return result


def _error(status_code, message):
    return JSONResponse(status_code=status_code, content={"success": False, "error": message})
