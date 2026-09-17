import logging
import threading
import time

import torch

from app.config import (
    TRANSLATION_MODEL_DIR,
    TRANSLATION_SOURCE_LANG,
    TRANSLATION_TARGET_LANG,
)

logger = logging.getLogger("translation_service")


class TranslationError(Exception):
    pass


_lock = threading.Lock()
_pipeline = None


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    with _lock:
        if _pipeline is not None:
            return _pipeline
        if not TRANSLATION_MODEL_DIR.exists():
            raise TranslationError(
                f"IndicTrans2 model not found at {TRANSLATION_MODEL_DIR}. "
                "Re-run the translation model setup."
            )
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            from IndicTransToolkit.processor import IndicProcessor

            tokenizer = AutoTokenizer.from_pretrained(
                str(TRANSLATION_MODEL_DIR), trust_remote_code=True
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(TRANSLATION_MODEL_DIR), trust_remote_code=True, torch_dtype=torch.float32
            )
            model.eval()
            processor = IndicProcessor(inference=True)
        except Exception as exc:
            raise TranslationError(f"Failed to load IndicTrans2: {exc}") from exc
        _pipeline = {"model": model, "tokenizer": tokenizer, "processor": processor}
        logger.info(
            "IndicTrans2 loaded from %s (%s -> %s)",
            TRANSLATION_MODEL_DIR.name,
            TRANSLATION_SOURCE_LANG,
            TRANSLATION_TARGET_LANG,
        )
    return _pipeline


def _translate_texts(texts, **gen_overrides):
    if not texts:
        return []
    pipeline = _load_pipeline()
    model = pipeline["model"]
    tokenizer = pipeline["tokenizer"]
    processor = pipeline["processor"]

    indices = [i for i, t in enumerate(texts) if t and t.strip()]
    results = ["" for _ in texts]
    if not indices:
        return results

    batch_input = [texts[i].strip() for i in indices]
    gen_kwargs = dict(
        use_cache=True,
        min_length=0,
        max_length=200,
        num_beams=1,
        num_return_sequences=1,
    )
    gen_kwargs.update(gen_overrides)
    with torch.no_grad():
        batch = processor.preprocess_batch(
            batch_input,
            src_lang=TRANSLATION_SOURCE_LANG,
            tgt_lang=TRANSLATION_TARGET_LANG,
        )
        inputs = tokenizer(
            batch,
            truncation=True,
            padding="longest",
            return_tensors="pt",
            return_attention_mask=True,
        )
        generated = model.generate(**inputs, **gen_kwargs)
        decoded = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        translated = processor.postprocess_batch(decoded, lang=TRANSLATION_TARGET_LANG)

    for idx, sat in zip(indices, translated):
        results[idx] = (sat or "").strip()
    return results


def translate_hindi_to_santali(texts):
    results = _translate_texts(texts)
    if any(not t for t, src in zip(results, texts) if src and src.strip()):
        raise TranslationError(
            "Empty Santali output for one or more Hindi strings. "
            "IndicTrans2 failed to translate some fields."
        )
    return results


def translate_batch_safe(texts):
    """Translate a batch, never raising on empty output.

    Each non-empty input gets one output slot; failed/empty translations come
    back as "". This lets the dictionary keep valid translations while clearly
    marking the individual failures as unavailable.
    """
    return _translate_texts(texts)


def translate_live(texts):
    """Live-classroom translation (shared IndicTrans2 singleton).

    Identical greedy decoding (``num_beams=1``, the deliberate latency choice
    for the classroom path) but with a repetition penalty that guards the known
    live bug where greedy IndicTrans2 output entered a repeating loop on
    ASR-fragmentary Santali text. The lesson-prep path (`_translate_texts`)
    is unchanged.
    """
    return _translate_texts(
        texts,
        repetition_penalty=1.3,
        no_repeat_ngram_size=4,
    )


def bilingualize(material):
    texts = []
    for q in material["worksheet"]["mcqs"]:
        texts.append(q["question"])
        texts.extend(q["options"])
        texts.append(q["correct_answer"])
        texts.append(q.get("explanation", ""))
    for q in material["worksheet"]["fill_in_the_blanks"]:
        texts.append(q["question"])
        texts.append(q["answer"])
    for q in material["worksheet"]["true_false"]:
        texts.append(q["statement"])
        texts.append("सही" if q["answer"] else "गलत")
        texts.append(q.get("explanation", ""))
    for f in material["flashcards"]:
        texts.append(f["front"])
        texts.append(f["back"])

    t0 = time.perf_counter()
    sat = translate_hindi_to_santali(texts)
    logger.info("translated %d strings in %.2fs", len(texts), time.perf_counter() - t0)

    i = 0
    for q in material["worksheet"]["mcqs"]:
        q["question_sat"] = sat[i]; i += 1
        q["options_sat"] = sat[i:i + len(q["options"])]; i += len(q["options"])
        q["correct_answer_sat"] = sat[i]; i += 1
        q["explanation_sat"] = sat[i]; i += 1
    for q in material["worksheet"]["fill_in_the_blanks"]:
        q["question_sat"] = sat[i]; i += 1
        q["answer_sat"] = sat[i]; i += 1
    for q in material["worksheet"]["true_false"]:
        q["statement_sat"] = sat[i]; i += 1
        q["answer_sat"] = sat[i]; i += 1
        q["explanation_sat"] = sat[i]; i += 1
    for f in material["flashcards"]:
        f["front_sat"] = sat[i]; i += 1
        f["back_sat"] = sat[i]; i += 1

    material["bilingual"] = True
    return material