# Bhasha Setu — Textbook Library Backend

Offline Hindi-textbook extraction backend for the Bhasha Setu classroom assistant.
Teacher uploads a Hindi textbook PDF, selects a page range, and the system extracts
clean Hindi text as JSON. Designed for low-RAM (~2 GB) offline classroom devices.

---

## 1. Architecture

```
teacher uploads PDF  →  saved to uploads/
                                    ↓
teacher selects pages  →  PyMuPDF opens PDF, reads only requested pages
                                    ↓
                              text cleaning (spaces, artifacts)
                                    ↓
                              structured JSON response
                                    ↓
                              cached on disk → reuse on repeated request
```

Key design decisions:
- **Never load the entire PDF into RAM.** PyMuPDF loads only the document catalog at open; individual pages are loaded on demand via `load_page()`.
- **Never extract the full book at upload time.** Only `page_count` is read (metadata only, no text).
- **Only requested pages are extracted.** Pages 10–15 means 6 `load_page` calls, not all N pages.
- **Cached results avoid re-processing.** Same textbook + same page range = serve from disk JSON.

---

## 2. Folder Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app + CORS
│   ├── config.py            ← path constants
│   ├── routes/
│   │   ├── __init__.py
│   │   └── textbook.py      ← upload + extract endpoints
│   └── services/
│       ├── __init__.py
│       └── pdf_extractor.py ← extraction, cleaning, caching
├── uploads/                  ← saved PDFs + metadata JSONs
├── extracted/                ← cached lesson JSONs per textbook
├── requirements.txt
├── make_sample_pdf.py        ← test PDF generator (run once)
├── README.md
└── .venv/                    ← Python virtual environment (created during setup)
```

---

## 3. Python Environment Setup

All commands are run from inside the `backend/` directory.

```bash
cd backend
```

**Create virtual environment:**
```bash
python -m venv .venv
```

**Activate it (Windows):**
```bash
.venv\Scripts\activate
```

**Activate it (Mac/Linux):**
```bash
source .venv/bin/activate
```

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt contents:**
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
PyMuPDF==1.25.1
python-multipart==0.0.20
```

Why these four:
- `fastapi` — lightweight HTTP framework
- `uvicorn[standard]` — ASGI server to run FastAPI
- `PyMuPDF` — fast PDF text extraction (the only PDF library)
- `python-multipart` — required by FastAPI for file uploads

---

## 5. Start the Server

From the `backend/` directory, with the virtual environment active:

```bash
uvicorn app.main:app --reload --port 8000
```

The `--reload` flag auto-restarts on code changes (dev convenience).
You should see output like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## 6. Generate a Test PDF (Optional)

To create a sample Hindi textbook for testing without a real PDF:

```bash
python make_sample_pdf.py
```

Creates `sample_hindi_textbook.pdf` (8 pages, Devanagari text).
Only works if a Devanagari font exists on your system (Nirmala UI on Windows).

---

## 7. Test Upload

```bash
curl -X POST http://127.0.0.1:8000/upload-textbook \
  -F "file=@sample_hindi_textbook.pdf"
```

**Response:**
```json
{
  "success": true,
  "textbook_id": "textbook_abc123def0",
  "filename": "sample_hindi_textbook.pdf",
  "total_pages": 8,
  "message": "Textbook uploaded. Select a page range to extract."
}
```

---

## 8. Test Page Extraction

Replace `textbook_abc123def0` with the ID from the upload response:

```bash
curl -X POST http://127.0.0.1:8000/extract-content \
  -H "Content-Type: application/json" \
  -d '{"textbook_id":"textbook_abc123def0","from_page":2,"to_page":5}'
```

**Response:**
```json
{
  "success": true,
  "textbook_id": "textbook_abc123def0",
  "filename": "sample_hindi_textbook.pdf",
  "from_page": 2,
  "to_page": 5,
  "total_pages": 8,
  "pages": [
    {
      "page_number": 2,
      "text": "पृष्ठ 2\n\nअध्याय 3 — पौधों में जीवन\n\nपौधे हमारी पृथ्वी के लिए बहुत महत्वपूर्ण हैं।...",
      "status": "ok"
    },
    {
      "page_number": 3,
      "text": "पृष्ठ 3\n\nअध्याय 3 — पौधों में जीवन\n\n...",
      "status": "ok"
    },
    {
      "page_number": 4,
      "text": "पृष्ठ 4\n\n...",
      "status": "ok"
    },
    {
      "page_number": 5,
      "text": "पृष्ठ 5\n\n...",
      "status": "ok"
    }
  ],
  "combined_text": "पृष्ठ 2\n\nअध्याय 3 — ...",
  "cached": false
}
```

**Second request for same range** returns `"cached": true` (no re-extraction).

---

## 9. Error Examples

**Invalid page range:**
```json
{
  "success": false,
  "error": "Page range exceeds textbook length. Textbook contains 80 pages."
}
```

**Non-existent textbook:**
```json
{
  "success": false,
  "error": "Textbook 'textbook_xyz' is not found. Upload it first."
}
```

**No extractable text on a page:**
```json
{
  "page_number": 25,
  "text": "",
  "status": "no_extractable_text"
}
```

---

## 10. Connect Your Existing Frontend

Add these two helper functions to your frontend. They replace the current
`setTimeout` mock calls in `ContentLibrary`:

```javascript
const API_BASE = "http://127.0.0.1:8000";

async function uploadTextbook(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload-textbook`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

async function extractContent(textbookId, fromPage, toPage) {
  const res = await fetch(`${API_BASE}/extract-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      textbook_id: textbookId,
      from_page: Number(fromPage),
      to_page: Number(toPage),
    }),
  });
  return res.json();
}
```

In your `ContentLibrary` component, modify `handleExtract`:

```javascript
const handleExtract = async () => {
  if (!pendingFile) return;           // pendingFile holds the actual File object
  setStatus("processing");

  const uploadRes = await uploadTextbook(pendingFile.file);
  if (!uploadRes.success) {
    setStatus("idle");
    alert(uploadRes.error);
    return;
  }

  const extractRes = await extractContent(uploadRes.textbook_id, fromPage, toPage);
  if (!extractRes.success) {
    setStatus("idle");
    alert(extractRes.error);
    return;
  }

  // Store the textbook_id so future requests can reuse it
  setTextbook({
    fileName: uploadRes.filename,
    textbook_id: uploadRes.textbook_id,
    fromPage,
    toPage,
    extracted: true,
    pages: extractRes.pages,
    combined_text: extractRes.combined_text,
  });
  setStatus("done");
};
```

**What to store in state:** Keep `textbook_id` from the upload response.
If you upload the same PDF for a different day's page range, you can reuse the
same `textbook_id` — only `from_page`/`to_page` changes, and the extract endpoint
handles everything.

---

## 11. Daily Content / JSON Update Strategy

**Recommended approach: Option B (cache small JSON per lesson on disk).**

Why Option B over Option A (generate on-the-fly every time):

| Factor | Option A (always generate) | Option B (cache to disk) |
|---|---|---|
| Repeated access (same day, multiple periods) | Re-extracts every time | Serves from disk instantly |
| RAM usage | Slightly higher per request | Nearly zero for repeat requests |
| Processing | Repeats work | Only first request processes |
| Disk cost | None | Small (a few KB per JSON) |
| Daily changes | Natural | Natural (new range = new file) |
| Old data cleanup | N/A | Prune files beyond a cap |

**How caching works here:**

Each unique `(textbook_id, from_page, to_page)` triple maps to one file:

```
extracted/
└── textbook_abc123def0/
    ├── pages_1_5.json
    ├── pages_6_10.json
    └── pages_11_15.json
```

- Same range requested again → served from `pages_1_5.json` with `"cached": true`
- New day, different range → new JSON file created
- Old files pruned automatically beyond 30 per textbook

**No unnecessary duplicates:** The filename includes the exact page range,
so requesting pages 1–5 twice creates only one file.

---

## 12. Memory / RAM Analysis (~2 GB constraint)

**Why PyMuPDF is suitable:**
PyMuPDF is a wrapper around MuPDF written in C. It uses lazy loading — opening a PDF
reads only the document catalog (cross-reference table, page tree root), typically
a few KB. Individual pages are loaded on demand when `load_page(i)` is called and
released when the variable goes out of scope.

**How page-by-page extraction works in RAM:**
For each page in the range:
1. `page = doc.load_page(idx)` — loads one page's text objects
2. `raw = page.get_text("text")` — extracts string (a few KB)
3. `page` variable goes out of scope at loop end → GC can reclaim memory

Only one page's data is "in flight" at any time. The `pages` list grows to hold
only the extracted strings (small — a few KB per page).

**Realistic RAM usage for a typical 80-page Hindi textbook PDF:**
- `fitz.open()` — opens the PDF catalog: typically 1–5 MB overhead (fonts, metadata)
- One loaded page — depends on page complexity; a text-heavy page is usually a few KB to tens of KB
- The `pages` list (e.g., 10 pages of extracted text) — typically 5–50 KB
- FastAPI + uvicorn server overhead — typically 20–50 MB at idle

**Potential bottlenecks:**
- **Embedded fonts with large glyph tables:** Some PDFs embed the entire font for each page. PyMuPDF caches font objects, which can increase memory with many different fonts. This is uncommon in typical Hindi textbook PDFs.
- **PDFs with embedded images:** `get_text("text")` ignores images, so image-heavy pages don't spike text extraction memory. However, PyMuPDF may still load image references into the document object. For our use case (text extraction only), this is negligible.
- **Very long extracted ranges:** Requesting pages 1–400 (the entire book) means holding 400 strings in memory. At ~5 KB each, this is ~2 MB — not a problem.

**Practical expectation:** For a typical Hindi textbook PDF (< 200 pages, text-based),
the backend should comfortably stay under 100 MB of RAM including the server overhead.
A 2 GB system has ample headroom. The main protection is that we never do
`doc.get_text()` on the entire document at once — only on the requested page range,
one page at a time.

---

## Where a Database Could Be Added Later

If teacher accounts, lesson history, or student progress tracking becomes necessary:

- **SQLite** — add `sqlite3` to requirements, create a `data/` directory for the `.db` file
- **Use case:** Store textbook metadata (instead of JSON files in `uploads/`)
- **Use case:** Store lesson history (which pages were taught on which date)
- **Use case:** Track flashcard scores for the `Misconceptions` component

The current filesystem-based approach is sufficient for single-teacher, single-device
use. Database becomes valuable when multiple teachers or devices need to share data.

---

## Future Pipeline (not implemented now)

```
Teacher Hindi speech → Hindi speech-to-text
                        ↓
              Hindi textbook content (this backend)
                        ↓
              Hindi → Santali translation
                        ↓
              Santali text → Santali speech output
```

This backend produces clean Hindi text that is ready to serve as input to a future
Hindi-to-Santali translation module. The text cleaning preserves Hindi structure
(headings, paragraphs, lists) which helps downstream translation quality.
