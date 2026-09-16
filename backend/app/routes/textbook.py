import json
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import UPLOAD_DIR, UPLOAD_CHUNK_SIZE
from app.services import pdf_extractor

router = APIRouter(tags=["textbook"])


class ExtractRequest(BaseModel):
    textbook_id: str
    from_page: int
    to_page: int


@router.post("/upload-textbook")
async def upload_textbook(file: UploadFile = File(...)):
    filename = file.filename or "textbook.pdf"
    if not _looks_like_pdf(file, filename):
        return _error(400, "Only PDF files are accepted.")

    textbook_id = f"textbook_{uuid.uuid4().hex[:10]}"
    pdf_path = UPLOAD_DIR / f"{textbook_id}.pdf"

    with pdf_path.open("wb") as out:
        shutil.copyfileobj(file.file, out, UPLOAD_CHUNK_SIZE)

    extractor = pdf_extractor.PdfExtractor(pdf_path)
    try:
        total_pages = extractor.page_count
    except Exception:
        pdf_path.unlink(missing_ok=True)
        return _error(400, "Uploaded file is not a valid PDF.")
    finally:
        extractor.close()

    meta = {
        "textbook_id": textbook_id,
        "filename": filename,
        "total_pages": total_pages,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    (UPLOAD_DIR / f"{textbook_id}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "success": True,
        "textbook_id": textbook_id,
        "filename": filename,
        "total_pages": total_pages,
        "message": "Textbook uploaded. Select a page range to extract.",
    }


@router.post("/extract-content")
def extract_content(req: ExtractRequest):
    meta_path = UPLOAD_DIR / f"{req.textbook_id}.json"
    pdf_path = UPLOAD_DIR / f"{req.textbook_id}.pdf"
    if not pdf_path.exists() or not meta_path.exists():
        return _error(404, f"Textbook '{req.textbook_id}' is not found. Upload it first.")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        total_pages = int(meta["total_pages"])
    except (json.JSONDecodeError, KeyError, OSError, ValueError):
        return _error(500, "Textbook metadata is missing or corrupted.")

    if req.from_page < 1:
        return _error(400, "from_page must be at least 1.")
    if req.to_page < req.from_page:
        return _error(400, "to_page cannot be smaller than from_page.")
    if req.to_page > total_pages:
        return _error(
            400,
            f"Page range exceeds textbook length. Textbook contains {total_pages} pages.",
        )

    payload = pdf_extractor.get_or_extract_lesson(
        pdf_path,
        req.textbook_id,
        req.from_page,
        req.to_page,
        meta.get("filename", ""),
        total_pages,
    )
    return payload


def _looks_like_pdf(file, filename):
    if not filename.lower().endswith(".pdf"):
        return False
    if file.content_type and file.content_type != "application/pdf":
        return False
    return True


def _error(status_code, message):
    return JSONResponse(status_code=status_code, content={"success": False, "error": message})