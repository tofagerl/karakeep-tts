"""Text-to-speech: chunking, OpenAI calls, MP3 concat, ID3 tagging."""
from __future__ import annotations
import re


def chunk_text(text: str, max_chars: int = 3800) -> list[str]:
    """Split text into chunks no longer than max_chars.

    Strategy: paragraphs first (split on blank lines), then sentences
    (split on .!?), then word boundaries. Raises ValueError if any
    single word exceeds max_chars (cannot be split safely).
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            flush()
            for piece in _split_paragraph(para, max_chars):
                chunks.append(piece)
            continue
        if len(current) + len(para) + 2 > max_chars:
            flush()
        current = (current + "\n\n" + para) if current else para

    flush()
    return chunks


def _split_paragraph(para: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", para)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_by_words(sent, max_chars))
            continue
        if len(current) + len(sent) + 1 > max_chars:
            chunks.append(current.strip())
            current = ""
        current = (current + " " + sent) if current else sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_by_words(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            raise ValueError(f"Word of length {len(word)} cannot be split into chunks of {max_chars}")
        if len(current) + len(word) + 1 > max_chars:
            chunks.append(current.strip())
            current = ""
        current = (current + " " + word) if current else word
    if current.strip():
        chunks.append(current.strip())
    return chunks
