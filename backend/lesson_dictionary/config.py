from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dictionary.db"

LESSONS_DIR = BASE_DIR / "lessons"
AUDIO_DIR = BASE_DIR / "audio"

TTS_MODEL_DIR = BASE_DIR.parent / "tts_models" / "indic-parler-tts"
# Official: ai4bharat/indic-parler-tts (gated on HuggingFace).
# Mirror used here is a verbatim Apache-2.0 re-upload of the same weights
# (config.json verified identical: vocab 90714, flan-t5-large, 24 layers).
# The previous mirror (naklitechie/indic-parler-tts) was deleted, which is why
# the earlier download was interrupted; RXD03/indic-parler-tts allows anonymous ACL.
TTS_MODEL_REPO = "RXD03/indic-parler-tts"

# Indic Parler-TTS uses TWO tokenizers: the prompt tokenizer (bundled with the
# model) and a separate description tokenizer (google/flan-t5-large). We keep a
# local copy so generation stays fully offline after one-time setup.
FLAN_T5_TOKENIZER_DIR = BASE_DIR.parent / "tts_models" / "flan-t5-large-tokenizer"
FLAN_T5_TOKENIZER_REPO = "google/flan-t5-large"

SAMPLE_RATE = 22050

HINDI_LANG = "hindi"
SANTALI_LANG = "santali"

for _d in (LESSONS_DIR, AUDIO_DIR):
    _d.mkdir(parents=True, exist_ok=True)