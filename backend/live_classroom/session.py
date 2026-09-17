"""Live-classroom session manager and orchestrator.

Replaces the `pipeline/orchestrator.py` worker with one that shares the app's
existing `translation_service` (IndicTrans2) and `lesson_dictionary.tts.TTSManager`
(Indic Parler-TTS) as singletons so model RAM/VRAM is never doubled.

Session lifecycle
    * ``LiveSession.start()``  — opens the mic, warms the shared MT pipeline
      in the background, and eagerly spawns a GPU fp16 TTS load in the same
      background thread.  The API returns immediately; the worker blocks on the
      TTS lock until the GPU load finishes.
    * ``LiveSession.stop()``   — stops capture/VAD, drains remaining segments,
      then unloads TTS (frees ~1.8 GB GPU) and calls ``gc.collect()`` /
      ``torch.cuda.empty_cache()``.

Design constraints (from the integration briefing):
    * Backlog is bounded (``config.BACKLOG_MAX``). Under sustained speech the
      OLDEST queued utterance is dropped so memory stays bounded and realtime
      behaviour is preserved.
    * VAD ``min_silence`` is raised to 1100 ms (vs the pipeline's 600 ms) to
      merge short pauses and reduce over-segmentation.
    * MT repetition bug: ``translation_service.translate_live`` adds
      ``repetition_penalty`` and ``no_repeat_ngram_size`` without changing the
      lesson-prep translation path.
    * TTS sample rate is an explicit, consistent 44.1 kHz end-to-end.
"""

from __future__ import annotations

import gc
import logging
import os
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import psutil
import soundfile as sf

from live_classroom import config
from live_classroom.asr import HindiASR
from live_classroom.capture import AudioCapture, VADSegmenter
from live_classroom.splitter import split_sentences

# ---------------------------------------------------------------------------
# lesson_dictionary / tts.py lives in its own package and is imported with the
# same sys.path trick used by routes/lesson_dictionary.py.
# ---------------------------------------------------------------------------
_LD_DIR = Path(__file__).resolve().parent.parent / "lesson_dictionary"
if str(_LD_DIR) not in sys.path:
    sys.path.insert(0, str(_LD_DIR))

from tts import TTSManager  # noqa: E402

# IndicTrans2 singleton (CPU float32; beams = 1)
from app.services import translation_service  # noqa: E402

logger = logging.getLogger("live_classroom")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LiveChunk:
    """One translated+synthesised sentence sent to the frontend."""
    index: int
    hindi: str
    santali: str
    asr_s: float
    mt_s: float
    tts_s: float
    queue_wait_s: float
    chunk_s: float       # wall time from VAD-end of speech to this result
    audio_url: str
    latency_target_met: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = "chunk"
        return d


@dataclass
class SessionStats:
    started_at: float = 0.0
    utterances: int = 0
    chunks: int = 0
    dropped_segments: int = 0
    avg_asr_s: float = 0.0
    avg_mt_s: float = 0.0
    avg_tts_s: float = 0.0
    peak_vram_mb: float = 0.0
    rss_mb: float = 0.0
    tts_loading: bool = False
    tts_loaded: bool = False
    mt_loaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["elapsed_s"] = time.time() - self.started_at if self.started_at else 0.0
        return d

# ---------------------------------------------------------------------------
# Bounded broadcast helpers
# ---------------------------------------------------------------------------
_broadcast_fn: Optional[Callable[[dict[str, Any]], None]] = None

def _broadcast(obj: dict[str, Any]) -> None:
    if _broadcast_fn is not None:
        try:
            _broadcast_fn(obj)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# LiveSession
# ---------------------------------------------------------------------------

class LiveSession:
    def __init__(
        self,
        session_id: str,
        device: Optional[int] = None,
    ) -> None:
        self.session_id = session_id
        self.device = device
        self._asr = HindiASR()
        self._capture = AudioCapture(device=device)
        self._segmenter = VADSegmenter(self._capture, on_segment=self._on_segment)
        self._work: queue.Queue[tuple[float, np.ndarray]] = queue.Queue(maxsize=config.BACKLOG_MAX)
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._stats = SessionStats(started_at=time.time())

        # TTS: loaded in a single serialized cold-start thread; worker blocks
        # on first call while the GPU load finishes.
        self._warmup_lock = threading.RLock()
        self._tts: Optional[TTSManager] = None
        self._tts_loading = False
        self._tts_error: Optional[str] = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._worker = threading.Thread(target=self._worker_loop, name="live-worker", daemon=True)
        self._worker.start()
        # One cold-start thread loads MT then TTS, holding the warmup lock for
        # the whole sequence. This serialises the first-time transformers
        # imports (concurrent first imports crash intermittently with
        # "cannot import name 'AutoConfig'") AND keeps /live/start instant.
        threading.Thread(target=self._cold_start, name="live-cold-start", daemon=True).start()
        self._capture.start()
        self._segmenter.start()

    def stop(self) -> None:
        self._stop.set()
        self._segmenter.stop()
        self._capture.stop()
        if self._worker is not None:
            self._worker.join(timeout=3.0)
        self._unload_tts()
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass

    # ------------------------------------------------------------------ warmup
    def _cold_start(self) -> None:
        """Load the shared MT singleton, then the GPU-fp16 TTS, serially.

        The whole sequence holds ``self._warmup_lock`` so the worker can never
        start loading heavy graph-capable libraries concurrently with this
        thread (parallel first-time ``transformers`` imports are the root cause
        of the intermittent ``AutoConfig`` ImportError).
        """
        with self._warmup_lock:
            try:
                translation_service._load_pipeline()
                self._stats.mt_loaded = True
            except Exception as exc:
                logger.warning("MT warm-up failed: %r", exc)
            try:
                self._ensure_tts()
            except Exception as exc:
                logger.error("TTS warm-up failed: %r", exc)
                self._tts_error = str(exc)

    def _ensure_tts(self) -> TTSManager:
        if self._tts is not None and self._tts.loaded:
            return self._tts
        with self._warmup_lock:
            if self._tts is not None and self._tts.loaded:
                return self._tts
            self._tts_loading = True
            try:
                dev = config.resolve_device(config.TTS_DEVICE)
                if (dev == "cuda" and config.TTS_FP16) or dev == "cuda":
                    import torch

                    dtype = torch.float16 if config.TTS_FP16 else torch.float32
                else:
                    import torch

                    dtype = torch.float32
                tts = TTSManager(device=dev, dtype=dtype, sample_rate=config.TTS_SAMPLE_RATE)
                tts.load()
                self._tts = tts
                self._stats.tts_loaded = True
            finally:
                self._tts_loading = False
        return self._tts

    def _unload_tts(self) -> None:
        with self._warmup_lock:
            if self._tts is not None:
                self._tts.unload()
                self._tts = None
                self._stats.tts_loaded = False

    # ------------------------------------------------------------------ capture -> queue
    def _on_segment(self, segment: np.ndarray) -> None:
        if self._stop.is_set():
            return
        item = (time.monotonic(), segment)
        try:
            self._work.put_nowait(item)
        except queue.Full:
            try:
                self._work.get_nowait()          # drop oldest
            except queue.Empty:
                pass
            try:
                self._work.put_nowait(item)
            except queue.Empty:
                pass
            self._stats.dropped_segments += 1

    # ------------------------------------------------------------------ worker
    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                enqueued_at, segment = self._work.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process_segment(segment, enqueued_at)
            except Exception as exc:
                logger.error("segment failed: %r", exc)

    def _process_segment(
        self, segment: np.ndarray, enqueued_at: float
    ) -> None:
        seg_start = time.monotonic()
        queue_wait_s = seg_start - enqueued_at

        t0 = time.monotonic()
        hindi = self._asr.transcribe(segment)
        asr_s = time.monotonic() - t0

        chunks: list[LiveChunk] = []
        idx = self._stats.chunks
        for hchunk in split_sentences(hindi):
            if not hchunk:
                continue
            t1 = time.monotonic()
            santali = translation_service.translate_live([hchunk])[0]
            mt_s = time.monotonic() - t1
            if not santali:
                continue

            t2 = time.monotonic()
            audio = self._ensure_tts().synthesize_array(santali, "santali")
            tts_s = time.monotonic() - t2

            if len(audio) == 0:
                continue

            wav_path = self._save_wav(idx, audio)
            chunk_s = time.monotonic() - seg_start
            pkt = LiveChunk(
                index=idx,
                hindi=hchunk,
                santali=santali,
                asr_s=asr_s,
                mt_s=mt_s,
                tts_s=tts_s,
                queue_wait_s=queue_wait_s,
                chunk_s=chunk_s,
                audio_url=f"/live/audio/{self.session_id}/{idx}.wav",
                latency_target_met=chunk_s <= config.CHUNK_LATENCY_TARGET_S,
            )
            idx += 1
            chunks.append(pkt)
            _broadcast(pkt.to_dict())

        self._stats.utterances += 1
        self._stats.chunks = idx
        if chunks:
            n = self._stats.utterances
            self._stats.avg_asr_s = (
                (self._stats.avg_asr_s * (n - 1) + asr_s) / n
            )
            self._stats.avg_mt_s = (
                (self._stats.avg_mt_s * (n - 1) + np.mean([c.mt_s for c in chunks])) / n
            )
            self._stats.avg_tts_s = (
                (self._stats.avg_tts_s * (n - 1) + np.mean([c.tts_s for c in chunks])) / n
            )
        self._update_vram_stats()

    def _save_wav(self, idx: int, audio: np.ndarray) -> Path:
        out_dir = config.LIVE_AUDIO_DIR / self.session_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{idx}.wav"
        sf.write(str(path), audio, config.TTS_SAMPLE_RATE)
        return path

    def _update_vram_stats(self) -> None:
        try:
            import torch
            if torch.cuda.is_available():
                self._stats.peak_vram_mb = max(
                    self._stats.peak_vram_mb,
                    torch.cuda.max_memory_allocated() / (1024 * 1024),
                )
        except Exception:
            pass
        self._stats.rss_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

    def status_data(self) -> dict[str, Any]:
        self._update_vram_stats()
        d = self._stats.to_dict()
        d.update(
            {
                "active": True,
                "session_id": self.session_id,
                "tts_loading": self._tts_loading,
                "tts_error": self._tts_error,
            }
        )
        return d


# ---------------------------------------------------------------------------
# Singleton manager (router-level)
# ---------------------------------------------------------------------------

class LiveSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: Optional[LiveSession] = None

    def active(self) -> bool:
        with self._lock:
            return self._session is not None

    def start(self, session_id: str, device: Optional[int] = None) -> LiveSession:
        with self._lock:
            if self._session is not None:
                raise RuntimeError("A live session is already active.")
            self._session = LiveSession(session_id, device=device)
            self._session.start()
            return self._session

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._session is None:
                raise RuntimeError("No live session is active.")
            session = self._session
            self._session = None
        session.stop()
        stats = session.status_data()
        stats["active"] = False
        return stats

    def get(self) -> Optional[LiveSession]:
        with self._lock:
            return self._session

    def status_data(self) -> dict[str, Any]:
        with self._lock:
            if self._session is None:
                return {"active": False}
            return self._session.status_data()

    def on_chunk(self, chunk: dict[str, Any]) -> None:
        _broadcast(chunk)


# Module singleton
session_manager = LiveSessionManager()