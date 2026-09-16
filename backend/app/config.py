from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
EXTRACTED_DIR = BASE_DIR / "extracted"
GENERATED_DIR = BASE_DIR / "generated"
MODELS_DIR = BASE_DIR / "models"

UPLOAD_CHUNK_SIZE = 256 * 1024
MAX_CACHED_LESSONS = 30
MAX_CACHED_MATERIAL = 30

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_PATH = MODELS_DIR / MODEL_FILENAME

TRANSLATION_ENABLED = True
TRANSLATION_REQUIRED = True
TRANSLATION_MODEL_NAME = "ai4bharat/indictrans2-indic-indic-dist-320M"
TRANSLATION_MODEL_DIR = BASE_DIR / "translation_models" / "indictrans2-indic-indic-dist-320M"
TRANSLATION_SOURCE_LANG = "hin_Deva"
TRANSLATION_TARGET_LANG = "sat_Olck"

LLM_N_CTX = 3072
LLM_MAX_TOKENS = 2048
LLM_TEMPERATURE = 0.6
LLM_TOP_P = 0.9
CHUNK_MAX_CHARS = 1400
MAX_INPUT_CHARS = 700

GENERATION_QUOTAS = {
    "mcqs": 5,
    "fill_in_the_blanks": 3,
    "true_false": 2,
    "flashcards": 5,
}

for _d in (UPLOAD_DIR, EXTRACTED_DIR, GENERATED_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
