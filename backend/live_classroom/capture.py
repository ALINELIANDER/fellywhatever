"""Live-classroom audio capture + automatic VAD segmentation.

Port of `pipeline/capture.py` into the Bhasha Setu backend with absolute
package imports.  The microphone is opened once and never stopped while the
live class session is active. A PortAudio callback pushes fixed 512-sample
blocks into a bounded queue; a dedicated VAD thread consumes that queue and
emits complete utterances (on speech-pause boundaries) to the worker queue.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Callable, Iterator, Optional

import numpy as np
import sys

from live_classroom import config

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover
    raise ImportError("sounddevice is required for audio capture") from exc

try:
    import torch
    from silero_vad import load_silero_vad
except ImportError as exc:  # pragma: no cover
    raise ImportError("silero-vad and torch are required for VAD") from exc


class _Decimator:
    """Streaming FIR decimation for integer ratios, e.g. 48 kHz -> 16 kHz."""

    def __init__(self, q: int) -> None:
        from scipy.signal import firwin, lfilter

        self.q = q
        self.h = firwin(64 * q + 1, 1.0 / q).astype(np.float64)
        self.zi = np.zeros(len(self.h) - 1, dtype=np.float64)
        self.phase = 0
        self._lfilter = lfilter

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self.zi = self._lfilter(
            self.h, 1.0, np.asarray(x, dtype=np.float64), zi=self.zi
        )
        n = y.shape[0]
        start = (self.q - self.phase) % self.q
        out = y[start:: self.q]
        self.phase = (self.phase + n) % self.q
        return out.astype(np.float32)


class AudioCapture:
    """Rolling, non-blocking 16 kHz mono capture from the default input device."""

    def __init__(
        self,
        sample_rate: int = config.ASR_SAMPLE_RATE,
        block_frames: int = config.VAD_BLOCK_FRAMES,
        device: Optional[int] = None,
        buffer_seconds: float = config.CAPTURE_BUFFER_S,
        queue_max: int = config.CAPTURE_QUEUE_MAX,
        channels: Optional[int] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_frames = block_frames
        self.device = config.INPUT_DEVICE if device is None else device
        self.buffer_seconds = buffer_seconds
        self.channels = channels if channels is not None else config.CAPTURE_CHANNELS

        self._queue: "queue.Queue[tuple[int, np.ndarray]]" = queue.Queue(
            maxsize=queue_max
        )
        self._ring: deque[tuple[int, np.ndarray]] = deque()
        self._ring_frames = 0
        self.max_ring_frames = int(buffer_seconds * sample_rate)
        self._lock = threading.Lock()
        self._total_frames = 0
        self._stream: Optional[sd.InputStream] = None
        self._resampler: Optional[_Decimator] = None
        self._capture_rate = sample_rate
        self._closed = threading.Event()

    def _pick_capture_rate(self) -> int:
        """Prefer 16 kHz directly; fall back to an integer multiple (e.g. 48 kHz)."""
        ch = max(1, self.channels)
        args = dict(
            samplerate=self.sample_rate,
            channels=ch,
            dtype="float32",
            device=self.device,
        )
        try:
            sd.check_input_settings(**args)
            return self.sample_rate
        except Exception:
            pass
        try:
            info = sd.query_devices(self.device)
            default = int(info["default_samplerate"])
        except Exception as exc:
            raise ValueError(
                f"cannot query input device {self.device}: {exc}"
            ) from exc
        if default >= self.sample_rate and default % self.sample_rate == 0:
            try:
                sd.check_input_settings(
                    samplerate=default,
                    channels=ch,
                    dtype="float32",
                    device=self.device,
                )
                return default
            except Exception as exc:
                raise ValueError(
                    f"device {self.device} rejects its own default rate {default}: "
                    f"{exc}"
                ) from exc
        raise ValueError(
            f"no supported capture samplerate for device {self.device} "
            f"(default {default}); needs 16000 or an integer multiple"
        )

    # -- lifecycle ---------------------------------------------------------
    def _init_com_for_wasapi(self) -> None:
        """Initialise COM (MTA) on this thread so WASAPI streams can start.

        FastAPI runs sync route handlers on threadpool workers where COM is not
        initialised; PortAudio's WASAPI stream start then fails with
        ``PaErrorCode -9999 / WdmSyncIoctl`` unless this thread joined the MTA.
        """
        if sys.platform != "win32" or getattr(self, "_com_initialised", False):
            return
        import ctypes

        COINIT_MTA = 0x0
        RPC_E_CHANGED_MODE = 0x80010106
        try:
            hr = ctypes.windll.ole32.CoInitializeEx(None, COINIT_MTA)
            # S_OK/S_FALSE => this thread joined (or already had) that apartment.
            # RPC_E_CHANGED_MODE => a different apartment was already active on
            # this thread; leave it alone (that state also opens fine).
            if (hr & 0xFFFFFFFF) in (0x0, 0x1, RPC_E_CHANGED_MODE):
                self._com_initialised = True
        except Exception:
            pass

    def start(self) -> None:
        self._init_com_for_wasapi()
        self._capture_rate = self._pick_capture_rate()
        if self._capture_rate == self.sample_rate:
            blocksize = self.block_frames
            self._resampler = None
        else:
            q = self._capture_rate // self.sample_rate
            blocksize = self.block_frames * q
            self._resampler = _Decimator(q)

        def make_stream(channels: int) -> sd.InputStream:
            return sd.InputStream(
                samplerate=self._capture_rate,
                blocksize=blocksize,
                channels=channels,
                dtype="float32",
                device=self.device,
                latency="low",
                callback=self._callback,
            )

        try:
            self._stream = make_stream(self.channels)
        except Exception as exc:
            if self.channels > 1:
                print(
                    f"[capture] stereo rejected on device {self.device}; "
                    f"retrying mono: {exc}"
                )
                self.channels = 1
                self._stream = make_stream(1)
            else:
                raise
        self._stream.start()
        self._warn_if_silent()

    def _warn_if_silent(self) -> None:
        """Print the live input level shortly after open; flag a dead endpoint."""
        min_frames = max(int(0.25 * self.sample_rate), 1)
        deadline = time.monotonic() + 3.0
        while True:
            with self._lock:
                frames = sum(len(b) for _, b in self._ring)
            if frames >= min_frames or time.monotonic() >= deadline:
                break
            time.sleep(0.15)
        with self._lock:
            frames, samples = 0, 0.0
            for _, block in self._ring:
                frames += len(block)
                samples += float(np.dot(block, block))
        if frames < min_frames:
            print(
                f"[capture] device {self.device} @ {self._capture_rate} Hz "
                f"{self.channels}ch -> NO SAMPLES YET  <-- CHECK DEVICE"
            )
            return
        rms = float(np.sqrt(samples / frames))
        flag = "" if rms >= config.CAPTURE_RMS_WARN_FLOOR else "  <-- SUSPICIOUSLY SILENT"
        print(
            f"[capture] device {self.device} @ {self._capture_rate} Hz "
            f"{self.channels}ch -> live RMS {rms:.6f}{flag}"
        )

    def stop(self) -> None:
        self._closed.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

    # -- PortAudio callback ------------------------------------------------
    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            pass
        try:
            mat = np.ascontiguousarray(indata, dtype=np.float32)
            if mat.ndim > 1 and mat.shape[1] > 1:
                mono = mat.mean(axis=1)
            else:
                mono = mat[:, 0] if mat.ndim > 1 else mat
            mono = np.ascontiguousarray(mono, dtype=np.float32)
            if self._resampler is not None:
                mono = self._resampler.process(mono)
        except Exception:
            return
        self._push(0, mono)

    # -- internal buffer management ---------------------------------------
    def _push(self, _abs_ignored: int, mono: np.ndarray) -> None:
        with self._lock:
            start = self._total_frames
            self._total_frames += len(mono)
            item = (start, mono)
            self._ring.append(item)
            self._ring_frames += len(mono)
            while self._ring_frames > self.max_ring_frames and len(self._ring) > 1:
                _, old = self._ring.popleft()
                self._ring_frames -= len(old)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(item)
            except queue.Empty:
                pass

    # -- consumer API ------------------------------------------------------
    def iter_chunks(self, timeout: float = 0.5) -> Iterator[tuple[int, np.ndarray]]:
        """Yield ``(abs_start_frame, block)`` until the capture is stopped."""
        while not self._closed.is_set():
            try:
                yield self._queue.get(timeout=timeout)
            except queue.Empty:
                continue

    def inject(self, mono: np.ndarray) -> None:
        """Test hook: feed audio as if it came from the microphone."""
        mono = np.ascontiguousarray(mono, dtype=np.float32)
        block = self.block_frames
        for i in range(0, len(mono), block):
            self._push(0, mono[i : i + block])
        if self._closed.is_set():
            return


class VADSegmenter:
    """Turns the continuous block stream into complete utterances."""

    def __init__(
        self,
        capture: AudioCapture,
        threshold: float = config.VAD_THRESHOLD,
        min_silence_ms: int = config.VAD_MIN_SILENCE_MS,
        min_speech_ms: int = config.VAD_MIN_SPEECH_MS,
        speech_pad_ms: int = config.VAD_SPEECH_PAD_MS,
        max_segment_s: float = config.VAD_MAX_SEGMENT_S,
        on_segment: Optional[Callable[[np.ndarray], None]] = None,
    ) -> None:
        self.capture = capture
        self.sample_rate = capture.sample_rate
        self.threshold = threshold
        self.min_silence_frames = int(min_silence_ms / 1000 * self.sample_rate)
        self.min_speech_frames = int(min_speech_ms / 1000 * self.sample_rate)
        self.speech_pad_frames = int(speech_pad_ms / 1000 * self.sample_rate)
        self.max_segment_frames = int(max_segment_s * self.sample_rate)
        self.on_segment = on_segment

        self.vad = load_silero_vad()
        self.segments: "queue.Queue[np.ndarray]" = queue.Queue()

        self._pre_roll_max = self.speech_pad_frames * 2
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vad", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # -- processing --------------------------------------------------------
    def _run(self) -> None:
        state = _SegmentState(self)
        for _abs_start, chunk in self.capture.iter_chunks():
            if self._stop.is_set():
                break
            self.process_chunk(chunk, state)
        seg = state.flush()
        if seg is not None:
            self._emit(seg)

    def process_chunk(self, chunk: np.ndarray, state: "_SegmentState") -> None:
        if len(chunk) == 0:
            return
        tensor = torch.from_numpy(np.ascontiguousarray(chunk, dtype=np.float32))
        prob = float(self.vad(tensor, self.sample_rate).item())
        state.push(chunk, prob)
        seg = state.maybe_finish()
        if seg is not None:
            self._emit(seg)

    def _emit(self, segment: np.ndarray) -> None:
        if segment is None or len(segment) < self.min_speech_frames:
            return
        if self.on_segment is not None:
            self.on_segment(segment)
        self.segments.put(segment)


class _SegmentState:
    """Per-stream VAD state machine."""

    def __init__(self, seg: VADSegmenter) -> None:
        self.seg = seg
        self.speaking = False
        self.frames: list[np.ndarray] = []
        self.total = 0
        self.speech_frames = 0
        self.frames_at_last_speech = 0
        self.silence_frames = 0
        self._pre_roll: deque[np.ndarray] = deque()
        self._pre_roll_frames = 0

    def push(self, chunk: np.ndarray, prob: float) -> None:
        if prob >= self.seg.threshold:
            if not self.speaking:
                self.speaking = True
                self._seed_pre_roll()
            self.frames.append(chunk)
            self.total += len(chunk)
            self.speech_frames += len(chunk)
            self.frames_at_last_speech = self.total
            self.silence_frames = 0
        elif self.speaking:
            self.frames.append(chunk)
            self.total += len(chunk)
            self.silence_frames += len(chunk)
        else:
            self._remember_pre_roll(chunk)

    def maybe_finish(self) -> Optional[np.ndarray]:
        if not self.speaking:
            return None
        if self.silence_frames >= self.seg.min_silence_frames:
            return self._finalize()
        if self.total >= self.seg.max_segment_frames:
            return self._finalize(keep_speaking=True)
        return None

    def flush(self) -> Optional[np.ndarray]:
        if self.speaking and self.frames:
            return self._finalize()
        return None

    def _finalize(self, keep_speaking: bool = False) -> Optional[np.ndarray]:
        cut = min(self.total, self.frames_at_last_speech + self.seg.speech_pad_frames)
        audio = np.concatenate(self.frames)[:cut]
        ok = self.speech_frames >= self.seg.min_speech_frames
        self.frames = []
        self.total = 0
        self.speech_frames = 0
        self.frames_at_last_speech = 0
        self.silence_frames = 0
        self._pre_roll.clear()
        if not keep_speaking:
            self.speaking = False
            self.seg.vad.reset_states()
        return audio if ok else None

    def _remember_pre_roll(self, chunk: np.ndarray) -> None:
        self._pre_roll.append(chunk)
        self._pre_roll_frames += len(chunk)
        while self._pre_roll_frames > self.seg._pre_roll_max and len(self._pre_roll) > 1:
            old = self._pre_roll.popleft()
            self._pre_roll_frames -= len(old)

    def _seed_pre_roll(self) -> None:
        if self._pre_roll:
            self.frames = list(self._pre_roll)
            self.total = sum(len(c) for c in self.frames)
            self.frames_at_last_speech = self.total
        self._pre_roll.clear()
        self._pre_roll_frames = 0