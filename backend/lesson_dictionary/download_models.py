"""One-time setup: download the Indic Parler-TTS model into backend/tts_models/.

After this completes, every later run is fully offline.
Usage (from backend/):
    python lesson_dictionary/download_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tts import TTSManager


def main():
    tts = TTSManager()
    try:
        path = tts.ensure_model_dir()
        print(f"Model ready at: {path}")
        print("Offline copy complete — classroom runs need no internet.")
    except Exception as exc:
        print(f"Model download failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())