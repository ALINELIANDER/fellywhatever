"""Live-classroom runtime config (port of the pipeline's live path).

Decreed in the integration briefing:
  * ASR stays on CPU (onnxruntime session, already fast).
  * MT reuses the app's shared IndicTrans2 singleton (CPU float32); beams stay
    at 1 (deliberate latency choice) with repetition guards added in
    `translation_service.translate_live`.
  * TTS reuses the app's shared `lesson_dictionary.tts.TTSManager` on GPU fp16
    at an explicit 44.1 kHz, loaded once when the class starts and unloaded
    when it ends (resident for the whole session).
  * The ~20-45 s per-chunk band is the accepted prototype latency; the target
    below is a REPORTING flag only.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.config import BASE_DIR as APP_BASE_DIR

# ASR model lives inside this package (junction into project/models/asr/hi).
ASR_DIR = Path(__file__).resolve().parent / "models" / "asr" / "hi"

# ---------------------------------------------------------------------------
# Stage 1: capture + VAD segmentation
# ---------------------------------------------------------------------------
ASR_SAMPLE_RATE = 16000
CAPTURE_CHANNELS = int(os.environ.get("LIVE_CAPTURE_CHANNELS", "2"))
# WASAPI "Microphone Array (Realtek...)" index 9: stereo shared-mode capture
# (mono shared mode returns digital silence on this array), decimated to 16 kHz.
INPUT_DEVICE = int(os.environ.get("PIPELINE_INPUT_DEVICE", "9"))
CAPTURE_RMS_WARN_FLOOR = 1e-5

VAD_BLOCK_FRAMES = 512        # silero-vad expects 512 samples @ 16 kHz
VAD_THRESHOLD = 0.5
VAD_MIN_SILENCE_MS = 1100     # raised vs pipeline's 600 ms to merge short pauses
VAD_MIN_SPEECH_MS = 300
VAD_SPEECH_PAD_MS = 200
VAD_MAX_SEGMENT_S = 30.0      # force-cut runaway monologues
CAPTURE_BUFFER_S = 60.0
CAPTURE_QUEUE_MAX = 512

# ---------------------------------------------------------------------------
# Stage 3: MT (shared IndicTrans2 singleton; see translation_service)
# ---------------------------------------------------------------------------
MT_REPETITION_PENALTY = 1.3
MT_NO_REPEAT_NGRAM_SIZE = 4

# ---------------------------------------------------------------------------
# Stage 4: TTS (shared TTSManager; GPU fp16 for the live path)
# ---------------------------------------------------------------------------
TTS_SAMPLE_RATE = 44100       # explicit, consistent end-to-end
TTS_DEVICE = os.environ.get("LIVE_TTS_DEVICE", "auto")
TTS_FP16 = True
TTS_MAX_NEW_TOKENS = 80

# ---------------------------------------------------------------------------
# Orchestration / latency / backlog
# ---------------------------------------------------------------------------
CHUNK_MAX_CHARS = 80
CHUNK_MIN_CHARS = 20
CHUNK_LATENCY_TARGET_S = 45.0  # REPORTING flag only (accepted band ~20-45 s)

# Bounded utterance backlog. If the worker can't keep up (sustained speech),
# the OLDEST queued utterance is dropped so realtime behaviour is preserved and
# memory stays bounded. Dropped count is surfaced in /live/status.
BACKLOG_MAX = 3

LIVE_AUDIO_DIR = APP_BASE_DIR / "generated" / "live"


def resolve_device(prefer: str = "auto") -> str:
    """Return 'cuda' or 'cpu'. 'auto' inspects torch once (lazily)."""
    if prefer in ("cpu", "cuda"):
        return prefer
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"