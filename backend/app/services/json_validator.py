import json
import re


def extract_json(raw):
    """Pull the first balanced JSON object out of a model response string."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output.")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start : i + 1])
    raise ValueError("Unbalanced JSON object in model output.")


def _clean_str(value, default=""):
    if isinstance(value, str):
        return value.strip()
    return default


def _clean_bool(value, default=False):
    if isinstance(value, bool):
        return value
    return default


def _dedupe(items, key_fn):
    seen = set()
    out = []
    for item in items:
        key = key_fn(item)
        normalized = re.sub(r"\s+", " ", key or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(item)
    return out


def _normalize_mcq(item):
    question = _clean_str(item.get("question"))
    raw_options = item.get("options")
    options = []
    if isinstance(raw_options, list):
        for opt in raw_options:
            cleaned = _clean_str(opt)
            if cleaned:
                options.append(cleaned)
    correct = _clean_str(item.get("correct_answer"))
    explanation = _clean_str(item.get("explanation"))
    if not question or len(options) != 4 or not correct or correct not in options:
        return None
    return {
        "question": question,
        "options": options[:4],
        "correct_answer": correct,
        "explanation": explanation,
    }


def _normalize_fitb(item):
    question = _clean_str(item.get("question"))
    answer = _clean_str(item.get("answer"))
    if not question or "____" not in question or not answer:
        return None
    return {"question": question, "answer": answer}


def _normalize_tf(item):
    statement = _clean_str(item.get("statement"))
    answer = _clean_bool(item.get("answer"))
    explanation = _clean_str(item.get("explanation"))
    if not statement:
        return None
    return {"statement": statement, "answer": answer, "explanation": explanation}


def _normalize_flashcard(item):
    front = _clean_str(item.get("front"))
    back = _clean_str(item.get("back"))
    if not front or not back:
        return None
    return {"front": front, "back": back}


def validate_material(obj):
    """Validate and cleanse a generated worksheet+flashcards object.

    Returns (cleansed_object, errors). Individual malformed items are dropped
    and the remaining ones returned so the caller can decide whether to retry.
    """
    errors = []
    if not isinstance(obj, dict):
        return None, ["Model output is not a JSON object."]

    worksheet = obj.get("worksheet")
    if not isinstance(worksheet, dict):
        return None, ["Missing 'worksheet' object in model output."]

    mcqs = []
    raw_mcqs = worksheet.get("mcqs")
    if not isinstance(raw_mcqs, list):
        errors.append("'worksheet.mcqs' is missing.")
    else:
        for item in raw_mcqs:
            if not isinstance(item, dict):
                continue
            cleaned = _normalize_mcq(item)
            if cleaned:
                mcqs.append(cleaned)

    fitb = []
    raw_fitb = worksheet.get("fill_in_the_blanks")
    if not isinstance(raw_fitb, list):
        errors.append("'worksheet.fill_in_the_blanks' is missing.")
    else:
        for item in raw_fitb:
            if not isinstance(item, dict):
                continue
            cleaned = _normalize_fitb(item)
            if cleaned:
                fitb.append(cleaned)

    tf = []
    raw_tf = worksheet.get("true_false")
    if not isinstance(raw_tf, list):
        errors.append("'worksheet.true_false' is missing.")
    else:
        for item in raw_tf:
            if not isinstance(item, dict):
                continue
            cleaned = _normalize_tf(item)
            if cleaned:
                tf.append(cleaned)

    flashcards = []
    raw_flashcards = obj.get("flashcards")
    if not isinstance(raw_flashcards, list):
        errors.append("'flashcards' is missing.")
    else:
        for item in raw_flashcards:
            if not isinstance(item, dict):
                continue
            cleaned = _normalize_flashcard(item)
            if cleaned:
                flashcards.append(cleaned)

    mcqs = _dedupe(mcqs, lambda m: m["question"])
    fitb = _dedupe(fitb, lambda m: m["question"])
    tf = _dedupe(tf, lambda m: m["statement"])
    flashcards = _dedupe(flashcards, lambda m: m["front"])

    if not mcqs and not fitb and not tf and not flashcards:
        return None, errors or ["No usable questions generated."]

    return (
        {
            "worksheet": {
                "mcqs": mcqs,
                "fill_in_the_blanks": fitb,
                "true_false": tf,
            },
            "flashcards": flashcards,
        },
        errors,
    )


def counts_met(material):
    """Return a dict of category -> (produced, required)."""
    from app.config import GENERATION_QUOTAS

    worksheet = material["worksheet"]
    return {
        "MCQ": (len(worksheet["mcqs"]), GENERATION_QUOTAS["mcqs"]),
        "Fill in the blank": (
            len(worksheet["fill_in_the_blanks"]),
            GENERATION_QUOTAS["fill_in_the_blanks"],
        ),
        "True/False": (
            len(worksheet["true_false"]),
            GENERATION_QUOTAS["true_false"],
        ),
        "Flashcard": (len(material["flashcards"]), GENERATION_QUOTAS["flashcards"]),
    }
