"""Audio generation + playback for one lesson's dictionary entries.

- Safe, ASCII filenames derived from a simple Devanagari -> Latin slug.
- Only entries with a valid Santali translation get Santali audio.
- play_audio() just plays the local WAV file; it NEVER runs TTS.
"""

import hashlib
import re
import subprocess
from pathlib import Path

import database as db
from config import AUDIO_DIR

# Minimal Devanagari -> Latin map used only for filenames.
_MAP = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "क": "k", "ख": "kh",
    "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch", "छ": "chh", "ज": "j",
    "झ": "jh", "ञ": "ny", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
    "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y",
    "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s",
    "ह": "h", "ड़": "r", "ढ़": "rh", "ऍ": "e", "ऑ": "o", "क़": "q",
    "ग़": "g", "ज़": "z", "फ़": "f", "य़": "y",
}
_MATRA = {
    "ा": "a", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "े": "e",
    "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri", "ं": "n", "ँ": "n", "ः": "h",
}
_CONSONANT_RE = re.compile(r"[\u0915-\u0939\u0958-\u095f]")


def make_slug(word, fallback_index):
    slug = []
    prev_consonant = False
    for ch in word:
        if ch in _MAP:
            slug.append(_MAP[ch])
            prev_consonant = True
        elif ch in _MATRA:
            slug.append(_MATRA[ch])
            prev_consonant = False
        elif ch == "्":
            slug.append("")
            prev_consonant = True
        else:
            prev_consonant = False
    base = "".join(slug).strip("_")
    base = re.sub(r"[^a-z0-9]+", "", base.lower())
    if len(base) < 2:
        base = f"word{fallback_index:03d}"
    return base


def unique_slug(word, index, existing):
    base = make_slug(word, index)
    candidate = base
    n = 2
    while candidate in existing:
        suffix = hashlib.md5(word.encode("utf-8")).hexdigest()[:4]
        candidate = f"{base}_{suffix if n == 2 else str(n)}"
        n += 1
    existing.add(candidate)
    return candidate


def generate_lesson_audio(lesson_id, tts_manager=None, limit=None):
    """Generate WAV files for every entry of a lesson, then store paths in DB.

    `limit` caps the number of entries processed (e.g. 5 for a quick trial).
    Hidden behaviour: uses an in-memory `used` set so slugs never collide.
    Returns a summary dict.
    """
    entries = db.get_lesson_dictionary(lesson_id)
    if not entries:
        return {"lesson_id": lesson_id, "generated": 0, "skipped": 0, "files": []}
    if limit:
        entries = entries[:int(limit)]

    hindi_dir = AUDIO_DIR / lesson_id / "hindi"
    santali_dir = AUDIO_DIR / lesson_id / "santali"
    hindi_dir.mkdir(parents=True, exist_ok=True)
    santali_dir.mkdir(parents=True, exist_ok=True)

    owned = tts_manager if tts_manager is not None else _load_tts()
    generated = 0
    skipped = 0
    files = []
    used = set()

    try:
        for i, e in enumerate(entries, start=1):
            slug = unique_slug(e["hindi_word"], i, used)
            h_abs = hindi_dir / f"{slug}.wav"
            s_abs = santali_dir / f"{slug}.wav"

            hindi_rel = Path("audio") / lesson_id / "hindi" / f"{slug}.wav"
            santali_rel = None
            savailable = e.get("santali_word") and e["translation_status"] == "translated"

            owned.synthesize(e["hindi_word"], h_abs, "hindi")
            if savailable:
                owned.synthesize(e["santali_word"], s_abs, "santali")
                santali_rel = Path("audio") / lesson_id / "santali" / f"{slug}.wav"

            db.update_audio_paths(e["id"], str(hindi_rel), str(santali_rel))
            generated += 1
            files.append({"id": e["id"], "hindi": str(hindi_rel), "santali": str(santali_rel)})
            if not savailable:
                skipped += 1
    finally:
        if tts_manager is None:
            owned.unload()

    return {"lesson_id": lesson_id, "generated": generated, "skipped": skipped, "files": files}


def _load_tts():
    from tts import TTSManager

    return TTSManager().load()


def play_audio(audio_path):
    """Play a local WAV file on this machine. No TTS is involved."""
    p = Path(audio_path)
    if not p.is_absolute():
        p = db.DB_PATH.parent / p
    if not p.exists():
        raise FileNotFoundError(f"Audio file not found: {p}")
    if _is_windows():
        import winsound

        winsound.PlaySound(str(p), winsound.SND_FILENAME)
        return "played"
    subprocess.run(["ffplay", "-nodisp", "-autoexit", str(p)], check=False)
    return "played"


def _is_windows():
    import sys

    return sys.platform.startswith("win")