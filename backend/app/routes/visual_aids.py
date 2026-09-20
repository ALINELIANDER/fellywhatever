"""Content Library "Visual aids for today": upload / list / delete.

The uploaded image file is persisted under ``backend/uploads/visual_aids/``
(kept across restarts, same parent dir as uploaded textbooks), and the lesson
association + label metadata live in the shared SQLite dictionary database via
``app.services.visual_aids_db``. Images are returned to the frontend as data
URLs so the existing Visual aids UI (and the Live Classroom keyword matcher)
keep working without changes.
"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.config import UPLOAD_DIR
from app.services import visual_aids_db

router = APIRouter(tags=["visual-aids"])

_LESSON_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_AID_ID_RE = re.compile(r"^\d+$")
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _looks_like_image(filename) -> bool:
    ext = Path(filename or "").suffix.lower()
    return ext in _ALLOWED_EXT


def _data_url(file_bytes: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"


def _record_to_image(row, upload_root: Path) -> dict:
    img = {
        "id": row["id"],
        "lesson_id": row["lesson_id"],
        "label": row["label"],
        "fileName": row["file_name"],
        "mimeType": row["mime_type"],
    }
    file_path = Path(row["file_path"])
    if not file_path.is_absolute():
        file_path = upload_root / file_path
    try:
        img["dataUrl"] = _data_url(file_path.read_bytes(), row["mime_type"])
    except OSError:
        img["dataUrl"] = None
    return img


@router.post("/visual-aids")
async def create_visual_aid(
    lesson_id: str = Form(...),
    label: str = Form(...),
    file: UploadFile = File(...),
):
    if not _LESSON_ID_RE.fullmatch(lesson_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid lesson id."}
        )
    label = (label or "").strip()
    if not label:
        return JSONResponse(
            status_code=400, content={"success": False, "error": "A label is required."}
        )
    if len(label) > 120:
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Label is too long."}
        )
    filename = file.filename or "image.png"
    if not _looks_like_image(filename):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Only image files are accepted."},
        )

    mime_type = file.content_type or _MIME_BY_EXT[Path(filename).suffix.lower()]
    saved_name = f"{uuid.uuid4().hex[:12]}{Path(filename).suffix.lower()}"
    folder = UPLOAD_DIR / "visual_aids" / lesson_id
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / saved_name
    with out_path.open("wb") as out:
        import shutil

        shutil.copyfileobj(file.file, out)

    relative = Path("visual_aids") / lesson_id / saved_name
    row = visual_aids_db.insert_visual_aid(
        lesson_id, label, filename, str(relative), mime_type
    )
    if row is None:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Failed to save visual aid."},
        )
    return {
        "success": True,
        "image": _record_to_image(row, UPLOAD_DIR),
    }


@router.get("/visual-aids/{lesson_id}")
def list_visual_aids(lesson_id: str):
    if not _LESSON_ID_RE.fullmatch(lesson_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid lesson id."}
        )
    visual_aids_db.init_db()
    rows = visual_aids_db.list_visual_aids(lesson_id)
    return {
        "success": True,
        "lesson_id": lesson_id,
        "images": [_record_to_image(r, UPLOAD_DIR) for r in rows],
    }


@router.delete("/visual-aids/{aid_id}")
def delete_visual_aid(aid_id: str):
    if not _AID_ID_RE.fullmatch(aid_id):
        return JSONResponse(
            status_code=400, content={"success": False, "error": "Invalid id."}
        )
    row = visual_aids_db.delete_visual_aid(int(aid_id))
    if row is None:
        return JSONResponse(
            status_code=404, content={"success": False, "error": "Visual aid not found."}
        )
    file_path = Path(row["file_path"])
    if not file_path.is_absolute():
        file_path = UPLOAD_DIR / file_path
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
    return {"success": True}