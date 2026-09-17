"""Live-classroom sentence-level chunking for Hindi transcription output.

Port of `pipeline/splitter.py` with absolute package imports. Each sentence
is translated and synthesised on its own so output starts flowing in sentence-
size pieces rather than waiting for a whole utterance.
"""

from __future__ import annotations

import re

from live_classroom import config

_SENTENCE_SPLIT = re.compile(r"(?<=[।!?])\s*|\n+")


def split_sentences(
    text: str,
    max_chars: int = config.CHUNK_MAX_CHARS,
    min_chars: int = config.CHUNK_MIN_CHARS,
) -> list[str]:
    """Split Hindi text into chunk-size sentences."""
    text = (text or "").strip()
    if not text:
        return []

    raw = [piece for piece in _SENTENCE_SPLIT.split(text) if piece.strip()]
    if not raw:
        return []

    chunks: list[str] = []
    for piece in raw:
        piece = piece.strip()
        if chunks and len(piece) < min_chars and (
            len(chunks[-1]) + len(piece) + 1 <= max_chars
        ):
            chunks[-1] = f"{chunks[-1]} {piece}"
        else:
            chunks.append(piece)

    overflow: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            overflow.append(chunk)
            continue
        parts = chunk.split(" ")
        current = ""
        for part in parts:
            if not current:
                current = part
            elif len(current) + len(part) + 1 <= max_chars:
                current = f"{current} {part}"
            else:
                overflow.append(current)
                current = part
        if current:
            overflow.append(current)
    return [c for c in overflow if c.strip()]