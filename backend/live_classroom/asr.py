"""Live-classroom ASR stage: Hindi speech -> Hindi text.

Port of `pipeline/asr.py` (IndicConformer 120M, NeMo CTC, greedy decode) into
the Bhasha Setu backend, with absolute package imports. ASR stays on CPU
(already fast) to leave the GPU to MT/TTS.

The checkpoint is a *raw* NeMo CTC export whose inputs are log-mel features
(`audio_signal [B, 80, T]` plus a `length` tensor), NOT raw audio; this module
implements the model card's reference feature pipeline (preemphasis 0.97,
80-bin Slaney mel, `log(x + 2^-24)`, per-bin zero-mean/unit-var with ddof=1).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from live_classroom import config

try:
    import librosa
except ImportError as exc:  # pragma: no cover
    raise ImportError("librosa is required for the ASR feature front-end") from exc

try:
    import onnxruntime as ort
except ImportError as exc:  # pragma: no cover
    raise ImportError("onnxruntime is required for the ASR stage") from exc

PROVIDERS = ("CPUExecutionProvider",)

_PREEMPHASIS = 0.97
_LOG_OFFSET = 2 ** -24
_STD_EPSILON = 1e-5
_MAX_AUDIO_S = 120.0


def nemo_mel_features(
    audio: np.ndarray, sample_rate: int = config.ASR_SAMPLE_RATE
) -> np.ndarray | None:
    """NeMo-compatible ``[80, T]`` log-mel features (see module docstring)."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    if len(audio) == 0:
        return None
    audio = audio[: int(_MAX_AUDIO_S * sample_rate)]
    audio = np.concatenate([audio[:1], audio[1:] - _PREEMPHASIS * audio[:-1]])
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=sample_rate,
        n_fft=512,
        hop_length=160,
        win_length=400,
        n_mels=80,
        fmin=0,
        fmax=sample_rate / 2,
        norm="slaney",
        power=2.0,
    )
    log_mel = np.log(mel + _LOG_OFFSET).astype(np.float32)
    if log_mel.shape[1] < 2:  # std with ddof=1 needs at least 2 frames
        return None
    mean = log_mel.mean(axis=1, keepdims=True)
    std = log_mel.std(axis=1, ddof=1, keepdims=True) + _STD_EPSILON
    return ((log_mel - mean) / std).astype(np.float32)


def _greedy_ctc(logits: np.ndarray, vocab: list[str]) -> str:
    """Collapse repeated CTC tokens, drop blanks, map ids -> text."""
    log_probs = logits - logits.max(axis=-1, keepdims=True)
    log_probs = log_probs - np.log(np.exp(log_probs).sum(axis=-1, keepdims=True))
    ids = np.argmax(log_probs[0], axis=-1)
    blank = len(vocab)
    prev, tokens = -1, []
    for t in ids:
        if t == prev:
            continue
        if t != blank and 0 <= t < len(vocab):
            tokens.append(vocab[t])
        prev = t
    return "".join(tokens).replace("\u2581", " ").strip()


class HindiASR:
    """Hindi speech -> Hindi text via IndicConformer CTC (CPU)."""

    def __init__(
        self,
        model_dir: Path | str = config.ASR_DIR,
        num_threads: int = 4,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.num_threads = num_threads

        vocab_path = self.model_dir / "vocab.json"
        if not vocab_path.exists():
            raise FileNotFoundError(f"ASR vocab not found: {vocab_path}")
        with open(vocab_path, "r", encoding="utf-8") as fh:
            self.vocab: list[str] = json.load(fh)

        model_path = self.model_dir / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"ASR model not found: {model_path}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.num_threads
        options.inter_op_num_threads = 1
        available = set(ort.get_available_providers())
        providers = [p for p in PROVIDERS if p in available] or available
        self.session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=providers
        )

    def transcribe(self, samples: np.ndarray) -> str:
        """Transcribe mono float32 audio sampled at ``config.ASR_SAMPLE_RATE``."""
        if samples is None or len(samples) == 0:
            return ""
        features = nemo_mel_features(samples, config.ASR_SAMPLE_RATE)
        if features is None:
            return ""
        mel_batch = features[np.newaxis, :, :].astype(np.float32)
        mel_length = np.array([mel_batch.shape[2]], dtype=np.int64)
        logits = self.session.run(
            None, {"audio_signal": mel_batch, "length": mel_length}
        )[0]
        return _greedy_ctc(logits, self.vocab)