"""TTS benchmark for AI4Bharat Indic Parler-TTS on CPU.

Measures:
  - model download/load time
  - RAM used by the Python process before/after loading the model
  - Hindi word generation time
  - Santali word generation time
  - peak / total RAM
  - how the result compares against a ~2 GB budget

Usage (from backend/):
    python lesson_dictionary/benchmark_tts.py
    python lesson_dictionary/benchmark_tts.py --word जीवन --sat-word नाम
"""

import argparse
import gc
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _console
from tts import TTSManager


def rss_mb():
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        pass
    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        h = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.kernel32.GetProcessMemoryInfo(
            h, ctypes.byref(counters), counters.cb
        ):
            return counters.WorkingSetSize / (1024 * 1024)
    return None


def bench_word(tag, word, lang, manager):
    gc.collect()
    t0 = time.perf_counter()
    out = Path(f"_bench_{tag}.wav")
    manager.synthesize(word, out, lang)
    elapsed = time.perf_counter() - t0
    size = out.stat().st_size if out.exists() else 0
    out.unlink(missing_ok=True)
    return elapsed, size


def main():
    _console.enable_utf8()
    parser = argparse.ArgumentParser(description="Benchmark Indic Parler-TTS on CPU.")
    parser.add_argument("--word", default="पेड़")
    parser.add_argument("--sat-word", default="नाम")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    rss_before = rss_mb()
    print(f"[start]   RSS: {rss_before:.0f} MB" if rss_before else "[start]   RSS unavailable")

    tts = TTSManager()
    t_load0 = time.perf_counter()
    try:
        tts.load()
    except Exception as exc:
        print("\nBENCHMARK FAILED — could not load Indic Parler-TTS.")
        print(f"Reason: {exc}")
        print("\nNo RAM figures can be claimed for this model. Nothing further is measured.")
        return 1
    load_time = time.perf_counter() - t_load0

    rss_after = rss_mb()
    print(f"[load]    model load took {load_time:.1f}s")
    print(f"[load]    RSS after loading: {rss_after:.0f} MB" if rss_after else "[load]    RSS unavailable")
    if rss_before and rss_after:
        print(f"[load]    RAM delta from model: {rss_after - rss_before:.0f} MB")

    hin_times, sat_times = [], []
    try:
        for _ in range(max(1, args.repeat)):
            t, size = bench_word("hindi", args.word, "hindi", tts)
            hin_times.append(t)
            print(f"[hindi]   '{args.word}' -> {t:.2f}s (wav {size // 1024} KB)")
        for _ in range(max(1, args.repeat)):
            t, size = bench_word("santali", args.sat_word, "santali", tts)
            sat_times.append(t)
            print(f"[santali] '{args.sat_word}' -> {t:.2f}s (wav {size // 1024} KB)")
    finally:
        tts.unload()

    rss_end = rss_mb()
    print(f"[end]     RSS after unload: {rss_end:.0f} MB" if rss_end else "[end]     RSS unavailable")

    print("\n============== SUMMARY ==============")
    print(f"Model load time            : {load_time:.1f}s")
    print(f"RAM after model load       : {rss_after:.0f} MB" if rss_after else "RAM after load: n/a")
    if rss_before and rss_after:
        print(f"RAM increase (model)       : {rss_after - rss_before:.0f} MB")
    print(f"Hindi word generation (avg): {sum(hin_times) / len(hin_times):.2f}s")
    print(f"Santali word gen. (avg)    : {sum(sat_times) / len(sat_times):.2f}s"
          if sat_times else "Santali word gen: n/a")
    if rss_after and rss_after > 2048:
        print(f"\nVERDICT: measured RAM {rss_after:.0f} MB EXCEEDS the 2 GB budget. "
              "Do NOT ship this model on the target device.")
    elif rss_after and rss_after > 1024:
        print(f"\nVERDICT: measured RAM {rss_after:.0f} MB is within 2 GB but leaves little "
              "headroom on a 2 GB device. Use during preparation only.")
    elif rss_after:
        print(f"\nVERDICT: measured RAM {rss_after:.0f} MB fits comfortably in the 2 GB budget.")
    print("NOTE: model is unloaded by flip of a switch afterwards; it is never kept "
          "resident for the live classroom session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())