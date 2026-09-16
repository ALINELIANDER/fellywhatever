"""Santali translation layer, separated from the dictionary database.

Uses the locally downloaded IndicTrans2 model (hin_Deva -> sat_Olck) already
present in backend/translation_models. It NEVER fabricates translations:
words that fail or produce empty/garbage output are marked unavailable.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import translation_service


def _looks_translated(hindi, santali):
    if not santali or not santali.strip():
        return False
    sat = santali.strip()
    if len(sat) < 1:
        return False
    if sat == hindi.strip():
        return False
    if sat.replace(".", "").strip() == hindi.strip():
        return False
    if all(ch in " \u0900-\u097f" and ch in hindi for ch in sat[:3]) and len(sat) == len(hindi):
        return False
    return True


def translate_to_santali(items):
    """items: list of dicts with keys hindi_word, hindi_normalized.

    Returns the same list, enriched with 'santali_word' and 'translation_status'.
    Each word is evaluated independently: a failed translation only marks that
    word unavailable, it never discards the valid translations around it.
    """
    words = [it["hindi_word"] for it in items]
    try:
        translated = translation_service.translate_batch_safe(words)
    except Exception:
        translated = [""] * len(words)

    for it, sat in zip(items, translated):
        if _looks_translated(it["hindi_word"], sat):
            it["santali_word"] = sat.strip()
            it["translation_status"] = "translated"
        else:
            it["santali_word"] = None
            it["translation_status"] = "unavailable"
    return items


def translate_word(hindi_word):
    """Convenience for a single word (returns (santali, status))."""
    return translate_to_santali([{"hindi_word": hindi_word}])[0]