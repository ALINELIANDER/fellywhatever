"""Live Classroom endpoints: start/stop/status + WebSocket audio stream.

The audio pipeline (ASR -> MT -> TTS) runs server-side inside this FastAPI
process; the browser only receives JSON chunk messages plus audio at stable
URLs. WebSocket messages are JSON with ``type``; chunks look like:

    {"type": "chunk", "hindi": ..., "santali": ..., "audio_url": "...",
     "asr_s": ..., "mt_s": ..., "tts_s": ..., "chunk_s": ..., ...}

``audio_url`` is served by GET /live/audio/{session_id}/{n}.wav, proxied by
the Vite dev server on the /api prefix like every other route here.
"""

import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import BASE_DIR as APP_BASE_DIR

# Make live_classroom + lesson_dictionary importable (same trick the other
# routers use; uvicorn runs with backend/ on sys.path).
if str(APP_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(APP_BASE_DIR))

from live_classroom import config as lc_config  # noqa: E402
from live_classroom.session import session_manager  # noqa: E402

router = APIRouter(tags=["live-classroom"])

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# ---------------------------------------------------------------------------
# WebSocket fan-out (thread-safe via an asyncio.Queue per connected client;
# broadcast() may be called from worker threads).
# ---------------------------------------------------------------------------
_clients: set[asyncio.Queue] = set()


def _broadcast(obj) -> None:
    msg = json.dumps(obj, ensure_ascii=False)
    for q in list(_clients):
        q.put_nowait(msg)


# Route the session's chunk events into the socket fan-out.
import live_classroom.session as _lc_session  # noqa: E402

_lc_session._broadcast_fn = _broadcast


class StartRequest(BaseModel):
    device: int | None = None


def _session_details():
    if not session_manager.active():
        return {"active": False}
    data = session_manager.status_data()
    data["active"] = True
    return data


@router.post("/live/start")
def live_start(req: StartRequest | None = None):
    try:
        device = req.device if req else None
        session_id = uuid.uuid4().hex[:8]
        session_manager.start(session_id, device=device)
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})
    return {
        "success": True,
        "session_id": session_id,
        "message": "Live classroom started (mic + ASR running, TTS warming on GPU).",
        **session_manager.status_data(),
    }


@router.post("/live/stop")
def live_stop():
    try:
        stats = session_manager.stop()
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"success": False, "error": str(exc)})
    return {"success": True, "message": "Live classroom stopped; TTS unloaded.", **stats}


@router.get("/live/status")
def live_status():
    return {"success": True, **_session_details()}


@router.get("/live/audio/{session_id}/{filename}")
def live_audio(session_id: str, filename: str):
    if not _SESSION_ID_RE.fullmatch(session_id) or not _FILENAME_RE.fullmatch(filename):
        return JSONResponse(status_code=404, content={"success": False, "error": "Not found."})
    wav = (lc_config.LIVE_AUDIO_DIR / session_id / filename).resolve()
    if not wav.is_file() or lc_config.LIVE_AUDIO_DIR.resolve() not in wav.parents:
        return JSONResponse(status_code=404, content={"success": False, "error": "Audio not found."})
    return FileResponse(wav, media_type="audio/wav")


@router.websocket("/live/stream")
async def ws_live_stream(websocket: WebSocket):
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue()
    _clients.add(q)
    try:
        await websocket.send_text(
            json.dumps({"type": "welcome", **_session_details()}, ensure_ascii=False)
        )
    except Exception:
        _clients.discard(q)
        return

    async def _pump() -> None:
        try:
            while True:
                drained = []
                while True:
                    try:
                        drained.append(q.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                for item in drained:
                    await websocket.send_text(item)
                await asyncio.sleep(0.05)
        except Exception:
            pass

    pump_task = asyncio.create_task(_pump())
    try:
        while True:
            await websocket.receive_text()  # client->server messages are ignored
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _clients.discard(q)
        pump_task.cancel()