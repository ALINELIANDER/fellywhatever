"""Local-Qwen learning-material generation.

Strategy: the Qwen2.5-1.5B model follows English instructions much more
reliably than complex Hindi instructions, and long multi-item Hindi requests
degenerate. So each item section is generated in short, focused calls (English
instruction -> concise Hindi content) and the structured marker output is
parsed into the fixed JSON shape the frontend expects. One model instance is
loaded and reused for all calls.
"""

import os
import re
import threading
import time

from app.config import (
    CHUNK_MAX_CHARS,
    GENERATION_QUOTAS,
    LLM_MAX_TOKENS,
    LLM_N_CTX,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    MAX_INPUT_CHARS,
    MODEL_PATH,
)
from app.services import json_validator

REPEAT_PENALTY = 1.2
MAX_RETRIES_PER_ITEM = 1

_SYSTEM_PROMPT = (
    "You are a Hindi teacher assistant. Make learning material based ONLY on the "
    "given Hindi lesson text. Never add outside facts or new information. Write "
    "your answer ONLY in Hindi (Devanagari script), using very short simple Hindi "
    "words."
)

_ANSWER_LETTERS = {"क": 0, "ख": 1, "ग": 2, "घ": 3}

_lang_dirs = {}


class ModelUnavailable(Exception):
    pass


class GenerationError(Exception):
    pass


_llm = None
_model_error = None
_model_load_s = None
_lock = threading.Lock()


def _threads():
    return max(1, min(os.cpu_count() or 4, 16))


def model_load_seconds():
    return _model_load_s


def _get_llm():
    """Load one CPU-only model instance and reuse it for all requests."""
    global _llm, _model_error, _model_load_s
    if _llm is not None:
        return _llm
    if _model_error is not None:
        raise ModelUnavailable(_model_error)
    if not MODEL_PATH.exists():
        _model_error = (
            f"Qwen model file not found at: {MODEL_PATH}. "
            "Place qwen2.5-1.5b-instruct-q4_k_m.gguf in backend/models/."
        )
        raise ModelUnavailable(_model_error)

    with _lock:
        if _llm is not None:
            return _llm
        if _model_error is not None:
            raise ModelUnavailable(_model_error)
        try:
            from llama_cpp import Llama

            started = time.perf_counter()
            try:
                llm = Llama(
                    model_path=str(MODEL_PATH), n_ctx=LLM_N_CTX, n_batch=128,
                    n_threads=_threads(), n_gpu_layers=0, use_mmap=True, verbose=False,
                )
            except Exception:
                llm = Llama(
                    model_path=str(MODEL_PATH), n_ctx=LLM_N_CTX, n_batch=128,
                    n_threads=_threads(), n_gpu_layers=0, use_mmap=False, verbose=False,
                )
            _model_load_s = round(time.perf_counter() - started, 2)
            _llm = llm
            print(f"[qwen_generator] model loaded in {_model_load_s}s")
            return _llm
        except Exception as exc:
            _model_error = (
                f"Failed to load Qwen model: {exc}. The GGUF may be corrupt or the "
                "machine may not have enough free RAM (roughly 1.2-1.5 GB is needed)."
            )
            raise ModelUnavailable(_model_error)


def _dedupe_paragraphs(text):
    seen, blocks = set(), []
    for block in re.split(r"\n\s*\n", text or ""):
        block = block.strip()
        key = re.sub(r"\s+", "", block)
        if block and key not in seen:
            seen.add(key)
            blocks.append(block)
    return blocks


def _lesson_excerpt(text):
    """Fit one request into the low-RAM context window without more PDF reads."""
    blocks = _dedupe_paragraphs(text)
    content = "\n\n".join(blocks)
    max_chars = min(CHUNK_MAX_CHARS, MAX_INPUT_CHARS)
    if len(content) <= max_chars:
        return content
    picks = []
    for index in sorted({0, len(blocks) // 2, len(blocks) - 1}):
        if blocks[index] not in picks:
            picks.append(blocks[index])
    return "\n\n".join(picks)[:max_chars].rstrip()


def _chat(user_content, max_tokens):
    llm = _get_llm()
    with _lock:
        try:
            response = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=LLM_TEMPERATURE,
                top_p=LLM_TOP_P,
                max_tokens=max_tokens,
                repeat_penalty=REPEAT_PENALTY,
            )
        except Exception as exc:
            raise GenerationError(f"Qwen inference failed: {exc}") from exc
    try:
        content = response["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise GenerationError(f"Unexpected Qwen response structure: {exc}") from exc
    if not content.strip():
        raise GenerationError("Qwen returned an empty response.")
    return content


# -------------------------------------------------------------- MCQs


def _mcq_prompt(excerpt, prior=None):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE multiple choice question in Hindi. Use exactly this format:

प्रश्न: <question>

क) <option>

ख) <option>

ग) <option>

घ) <option>

उत्तर: <correct letter: क, ख, ग or घ>

Keep the question short and each option 2-5 words. Output only Hindi, nothing else."""


def _mcq_prompt_improved(excerpt, prior=None):
    prior_block = ""
    if prior:
        prior_block = (
            "\n\nAlready-generated questions about this lesson (do NOT repeat these "
            "and do NOT ask about the same fact again in different wording):\n"
            + "\n".join(f"- {p}" for p in prior)
        )
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE multiple choice question in simple Hindi for primary-school children. The question should test real understanding of the lesson (an important fact, or a why/how/comparison/order idea when the lesson supports it), NOT a trivial or isolated detail. Use exactly this format:

प्रश्न: <question>

क) <option>

ख) <option>

ग) <option>

घ) <option>

उत्तर: <correct letter: क, ख, ग or घ>

Rules:
- The question must be fully answerable from the lesson text above.
- The question must have a single, unambiguous correct answer; the three wrong options must be clearly wrong, not partly correct.
- Exactly one option (क, ख, ग or घ) is the clearly correct answer.
- All four options must be short (2-5 words each) and roughly similar in length.
- Distractors must be plausible and related to the lesson, never silly or random.
- Every detail in the question and options must come from the lesson; never invent facts or numbers.
- Write clear, grammatical, simple Hindi.
- Do not repeat a question you have already asked about this lesson.
{prior_block}
Output only Hindi, nothing else."""


def _parse_mcqs(raw):
    question_frag = re.search(r"प्रश्न\s*[:：\-–—]?\s*([^\n]+)", raw)
    if not question_frag:
        return None
    options = re.findall(r"^([कखगघ])\s*[)）\.।]\s*([^\n]+)$", raw, re.M)
    options = _clean_options(options)
    if len(options) != 4:
        return None
    answer = _parse_mcq_answer(raw, options)
    return {
        "question": question_frag.group(1).strip(),
        "options": options,
        "correct_answer": answer[1] if answer is not None else "",
        "explanation": "",
    }


def _clean_options(raw_pairs):
    out = []
    occupied = set()
    for letter, text in raw_pairs:
        text = text.strip()
        if text in occupied:
            continue
        occupied.add(text)
        out.append(text)
    return out[:4]


def _parse_mcq_answer(raw, options):
    letter_match = re.search(
        r"(?:उत्तर|सही उत्तर|अंसर|Answer|Uttar)\s*[:：]?\s*([कखगघ])", raw
    )
    if letter_match:
        index = _ANSWER_LETTERS.get(letter_match.group(1))
        if index is not None and index < len(options):
            return index, options[index]
    digit_match = re.search(
        r"(?:उत्तर|सही उत्तर|अंसर|Answer|Uttar)\s*[:：]?\s*([1-4])", raw
    )
    if digit_match:
        index = int(digit_match.group(1)) - 1
        if index < len(options):
            return index, options[index]
    answer_text = re.search(
        r"(?:उत्तर|सही उत्तर|अंसर|Answer|Uttar)\s*[:：]?\s*([^\n]+)", raw
    )
    if answer_text:
        text = answer_text.group(1).strip()
        for index, option in enumerate(options):
            if text == option or (text and option and text in option):
                return index, option
    return None


def _mcq_answer_letter_fallback(mcq):
    options_block = "\n".join(
        f"{letter}) {opt}" for letter, opt in zip("कखगघ", mcq["options"])
    )
    prompt = f"""MCQ in Hindi:

प्रश्न: {mcq["question"]}

{options_block}

Which option letter (क, ख, ग or घ) is the correct answer? Output only the single letter."""

    response = _chat(prompt, max_tokens=12)
    match = re.search(r"[कखगघ]", response)
    if not match:
        return False
    index = _ANSWER_LETTERS[match.group(0)]
    mcq["correct_answer"] = mcq["options"][index]
    return True


def _generate_mcqs(excerpt, quota, high_quality=False):
    items = []
    attempts_left = quota * (1 + MAX_RETRIES_PER_ITEM)
    prompt = _mcq_prompt_improved if high_quality else _mcq_prompt
    while len(items) < quota and attempts_left > 0:
        attempts_left -= 1
        try:
            raw = _chat(
                prompt(excerpt, prior=[m["question"] for m in items]),
                max_tokens=250,
            )
        except GenerationError:
            continue
        mcq = _parse_mcqs(raw)
        if mcq is None or mcq["question"] in {m["question"] for m in items}:
            continue
        if mcq["correct_answer"] not in mcq["options"]:
            try:
                if not _mcq_answer_letter_fallback(mcq):
                    continue
            except GenerationError:
                continue
        items.append(mcq)
    return items


# -------------------------------------------------------------- Fill in the blank


def _fitb_prompt(excerpt, prior=None):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE fill-in-the-blank question in Hindi. Use exactly this format:

प्रश्न: <one short Hindi sentence from the lesson with the key word replaced by ____>

उत्तर: <the word that fits in the blank>

Output only Hindi, nothing else."""


def _fitb_prompt_improved(excerpt, prior=None):
    prior_block = ""
    if prior:
        prior_block = (
            "\n\nAlready-generated fill-in-the-blank sentences about this lesson "
            "(do NOT repeat these sentences or re-use the same blanked word):\n"
            + "\n".join(f"- {p}" for p in prior)
        )
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE fill-in-the-blank sentence in simple Hindi for primary-school children. Use exactly this format:

प्रश्न: <one short Hindi sentence from the lesson with the key word replaced by ____>

उत्तर: <the word that fits in the blank>

Rules:
- The blanked word must be an important word that really appears in the lesson.
- The rest of the sentence must make the missing word clear and unambiguous.
- The answer must match the word in the lesson spell by spell.
- Never repeat a sentence you have already used for this lesson.
{prior_block}
Output only Hindi, nothing else."""


def _parse_fitb(raw):
    question_frag = re.search(r"प्रश्न\s*[:：\-–—]?\s*([^\n]+)", raw)
    if not question_frag:
        return None
    answer_frag = re.search(r"(?:उत्तर|अंसर|Answer)\s*[:：\-–—]?\s*([^\n]+)", raw)
    if not answer_frag:
        return None
    question = question_frag.group(1).strip()
    answer = answer_frag.group(1).strip()
    if not answer:
        return None
    if "____" not in question:
        if "___" in question:
            question = question.replace("___", "____")
        elif answer and answer.split() and answer.split()[0] in question:
            question = question.replace(answer.split()[0], "____", 1)
        else:
            question = question.rstrip(" .,।") + " ____।"
    return {"question": question, "answer": answer}


def _generate_fitb(excerpt, quota, high_quality=False):
    items = []
    attempts_left = quota * (1 + MAX_RETRIES_PER_ITEM)
    prompt = _fitb_prompt_improved if high_quality else _fitb_prompt
    while len(items) < quota and attempts_left > 0:
        attempts_left -= 1
        try:
            raw = _chat(
                prompt(excerpt, prior=[f["question"] for f in items]),
                max_tokens=120,
            )
        except GenerationError:
            continue
        fitb = _parse_fitb(raw)
        if fitb is None or fitb["question"] in {f["question"] for f in items}:
            continue
        items.append(fitb)
    return items


# -------------------------------------------------------------- True / False


def _tf_prompt(excerpt, prior=None):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, write ONE true/false statement in Hindi. Use exactly this format:

कथन: <a short Hindi statement based on the lesson>

उत्तर: <सही or गलत>

व्याख्या: <one short Hindi reason in 2-5 words>

Output only Hindi, nothing else."""


def _tf_prompt_improved(excerpt, prior=None):
    prior_block = ""
    if prior:
        prior_block = (
            "\n\nAlready-generated true/false statements about this lesson "
            "(do NOT repeat these or ask about the same fact again):\n"
            + "\n".join(f"- {p}" for p in prior)
        )
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, write ONE true/false statement in simple Hindi for primary-school children. Prefer a statement that tests real understanding of the lesson, not a trivial obvious fact. Use exactly this format:

कथन: <a short Hindi statement based on the lesson>

उत्तर: <सही or गलत>

व्याख्या: <one short Hindi reason in 2-5 words>

Rules:
- The statement must be fully answerable from the lesson text above.
- A false statement must still look plausible and related to the lesson, never silly.
- The reason (व्याख्या) must be supported by the lesson.
- Never repeat a statement you have already used for this lesson.
{prior_block}
Output only Hindi, nothing else."""


def _parse_tf(raw):
    statement_frag = re.search(r"कथन\s*[:：\-–—]?\s*([^\n]+)", raw)
    if not statement_frag:
        return None
    answer_match = re.search(
        r"(?:उत्तर|अंसर|Answer|Uttar)\s*[:：]?\s*(सही|गलत|सच|असत्य|True|False)",
        raw,
        re.IGNORECASE,
    )
    answer = True
    if answer_match:
        token = answer_match.group(1).lower()
        answer = token in ("सही", "सच", "true")
    explanation_frag = re.search(r"व्याख्या\s*[:：\-–—]?\s*([^\n]+)", raw)
    explanation = explanation_frag.group(1).strip() if explanation_frag else ""
    return {
        "statement": statement_frag.group(1).strip(),
        "answer": answer,
        "explanation": explanation,
    }


def _generate_tf(excerpt, quota, high_quality=False):
    items = []
    attempts_left = quota * (1 + MAX_RETRIES_PER_ITEM)
    prompt = _tf_prompt_improved if high_quality else _tf_prompt
    while len(items) < quota and attempts_left > 0:
        attempts_left -= 1
        try:
            raw = _chat(
                prompt(excerpt, prior=[t["statement"] for t in items]),
                max_tokens=150,
            )
        except GenerationError:
            continue
        tf_item = _parse_tf(raw)
        if tf_item is None or tf_item["statement"] in {t["statement"] for t in items}:
            continue
        items.append(tf_item)
    return items


# -------------------------------------------------------------- Flashcards


def _flashcards_prompt(excerpt):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create exactly {GENERATION_QUOTAS['flashcards']} flashcards in Hindi. Use this format for every flashcard:

सामने: <key term from the lesson>

पीछे: <short answer in 2-5 words>

Each flashcard is separated by a blank line. Output only Hindi, nothing else."""


def _flashcards_prompt_improved(excerpt):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create exactly {GENERATION_QUOTAS['flashcards']} flashcards in Hindi for primary-school children. Choose the most important words, terms and facts from the lesson (not common everyday words). Use this format for every flashcard:

सामने: <key term from the lesson>

पीछे: <short answer in 2-5 words>

Rules:
- The front must be a real key term from the lesson.
- The back must be a short, correct answer fully supported by the lesson.
- Never invent terms; never repeat a term twice.
Each flashcard is separated by a blank line. Output only Hindi, nothing else."""


def _parse_flashcards(raw):
    blocks = re.split(r"(?=सामने\s*[:：])", raw)
    cards = []
    for block in blocks:
        front = re.search(r"सामने\s*[:：]\s*([^\n]+)", block)
        back = re.search(r"पीछे\s*[:：]\s*([^\n]+)", block)
        if front and back:
            cards.append(
                {"front": front.group(1).strip(), "back": back.group(1).strip()}
            )
    return cards


def _flashcard_single_prompt(excerpt):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE flashcard in Hindi. Use exactly this format:

सामने: <key term from the lesson>

पीछे: <short answer in 2-5 words>

Output only Hindi, nothing else."""


def _flashcard_single_prompt_improved(excerpt):
    return f"""Hindi lesson:
{excerpt}

Based ONLY on this lesson, create ONE flashcard in Hindi for primary-school children. Choose an important term from the lesson (not a common everyday word). Use exactly this format:

सामने: <key term from the lesson>

पीछे: <short answer in 2-5 words>

Rules:
- The front must be a real key term from the lesson.
- The back must be short and correct, fully supported by the lesson.
- Never invent terms or repeat a term already used.
Output only Hindi, nothing else."""


def _generate_flashcards(excerpt, quota, high_quality=False):
    items = []
    try:
        prompt = _flashcards_prompt_improved if high_quality else _flashcards_prompt
        items = _parse_flashcards(_chat(prompt(excerpt), max_tokens=450))
    except GenerationError:
        items = []
    items = [
        card
        for card in items
        if card["front"] and card["back"]
    ]
    seen = set()
    unique = []
    for card in items:
        key = re.sub(r"\s+", "", card["front"])
        if key and key not in seen and len(unique) < quota:
            seen.add(key)
            unique.append(card)
    items = unique
    attempts_left = quota + MAX_RETRIES_PER_ITEM
    single_prompt = _flashcard_single_prompt_improved if high_quality else _flashcard_single_prompt
    while len(items) < quota and attempts_left > 0:
        attempts_left -= 1
        try:
            raw = _chat(single_prompt(excerpt), max_tokens=120)
        except GenerationError:
            continue
        card = re.search(
            r"सामने\s*[:：]\s*([^\n]+)\s+पीछे\s*[:：]\s*([^\n]+)", raw
        )
        if not card:
            continue
        front, back = card.group(1).strip(), card.group(2).strip()
        key = re.sub(r"\s+", "", front)
        if not front or not back or key in seen:
            continue
        seen.add(key)
        items.append({"front": front, "back": back})
    return items


# -------------------------------------------------------------- Top level


def generate_learning_material(text, high_quality=False, quotas=None):
    excerpt = _lesson_excerpt(text)
    if not excerpt.strip():
        raise GenerationError("No extractable text found in the selected pages.")

    quotas = {**GENERATION_QUOTAS, **(quotas or {})}
    started = time.perf_counter()
    calls = 0
    mcqs = _generate_mcqs(excerpt, quotas["mcqs"], high_quality)
    calls += len(mcqs)
    fitb = _generate_fitb(excerpt, quotas["fill_in_the_blanks"], high_quality)
    calls += len(fitb)
    tf = _generate_tf(excerpt, quotas["true_false"], high_quality)
    calls += len(tf)
    flashcards = _generate_flashcards(excerpt, quotas["flashcards"], high_quality)
    calls += 1

    material, errors = json_validator.validate_material(
        {
            "worksheet": {
                "mcqs": mcqs,
                "fill_in_the_blanks": fitb,
                "true_false": tf,
            },
            "flashcards": flashcards,
        }
    )
    if material is None:
        details = "; ".join(errors) if errors else "No usable items generated."
        raise GenerationError(f"Qwen output did not match the worksheet schema: {details}")
    if not material["worksheet"]["mcqs"]:
        raise GenerationError(
            "Qwen could not generate any valid multiple-choice questions from the "
            "selected pages. Try a different page range."
        )
    if not material["flashcards"]:
        raise GenerationError(
            "Qwen could not generate any valid flashcards from the selected pages. "
            "Try a different page range."
        )

    return material, {
        "model_load_s": _model_load_s,
        "excerpt_chars": len(excerpt),
        "inference_calls": calls,
        "inference_s": round(time.perf_counter() - started, 2),
    }