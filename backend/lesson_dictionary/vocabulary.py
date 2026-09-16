import re

from database import normalize_hindi

DEVANAGARI_RE = re.compile(r"^[\u0900-\u097f\u200c\u200d]+$")

NUMBERS = {"०", "१", "२", "३", "४", "५", "६", "७", "८", "९", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}

# Common Hindi function words (postpositions, conjunctions, pronouns, auxiliaries).
# Includes both the plain and the anusvara/chandrabindu forms so the stripped
# normalization still catches them.
STOPWORDS = {
    "है", "हैं", "था", "थी", "थे", "हुआ", "हुई", "हुए", "हो", "होते", "होता", "होती", "होंगे",
    "का", "की", "के", "को", "से", "में", "मे", "पर", "तक", "ने", "द्वारा", "और", "तथा", "एवं", "या",
    "अथवा", "लेकिन", "परन्तु", "किन्तु", "इस", "उस", "एक", "यह", "वह", "ये", "वे", "मैं", "तुम",
    "आप", "हम", "वही", "जो", "तो", "भी", "ही", "नहीं", "नही", "बहुत", "कुछ", "सभी", "सब", "आदि", "अब",
    "फिर", "तब", "जब", "कब", "क्यों", "किस", "किसने", "प्रति", "बिना", "बाद", "पहले", "अंदर",
    "बाहर", "ऊपर", "नीचे", "वाले", "वाला", "वाली", "कर", "करता", "करते", "करती", "होकर", "होने",
    "जाना", "आना", "देना", "लेना", "रहना", "रहता", "कोई", "किसी", "इन", "उन",
    "उन्हें", "इन्हें", "जैसे", "वैसे", "मतलब", "मतलबी", "जिसका", "जिसकी", "जिसके", "जिससे",
    "जिसे", "मुझे", "हमें", "हमे", "तुम्हें", "तुम्हे", "आपको", "खुद", "स्वयं", "अपना", "अपनी", "अपने",
    "चाहिए", "काफी", "ज्यादा", "थोड़ा", "थोडा", "इत्यादि", "मात्र",
    "हमारा", "हमारी", "हमारे", "तुम्हारा", "तुम्हारी", "तुम्हारे", "आपका", "आपकी", "आपके",
    "इसलिए", "इसका", "इसकी", "इसके", "उसका", "उसकी", "उसके", "उनका", "उनकी", "उनके",
    "यही", "वहीं", "जिनका", "जिनकी", "जिनके", "जिन्हें", "जिन्होंने",
    "पृष्ठ", "इसे", "चाहे", "मगर", "लिए", "बारे", "साथ",
}

PUNCT_RE = re.compile(r"[।॥,.!?;:'\"()\[\]{}\u201c\u201d\u2018\u2019\-–—_/\\|@#$%^&*+=~`<>«»]")

# Word rule: a run of Devanagari letters AND combining vowel signs (matras),
# plus ZWJ/ZWNJ used for half-consonants. `\w` alone does NOT match matras
# (Unicode category Mn), which previously split "जीवन" into "ज" + "वन".
TOKEN_RE = re.compile(r"[\u0900-\u097f\u200c\u200d]+")


def clean_lesson_text(text):
    text = PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_stopword(word):
    base = re.sub(r"[ंँः]", "", word)
    return word in STOPWORDS or base in STOPWORDS


def extract_vocabulary(text, max_words=None):
    """Return an ordered de-duplicated list of meaningful Hindi words."""
    cleaned = clean_lesson_text(text)
    seen = set()
    words = []
    for tok in TOKEN_RE.findall(cleaned):
        if not DEVANAGARI_RE.match(tok):
            continue
        if tok in NUMBERS:
            continue
        norm = normalize_hindi(tok)
        if not norm or len(norm) < 2:
            continue
        if norm in seen:
            continue
        if _is_stopword(tok):
            continue
        seen.add(norm)
        words.append({"hindi_word": tok, "hindi_normalized": norm})
        if max_words and len(words) >= max_words:
            break
    return words