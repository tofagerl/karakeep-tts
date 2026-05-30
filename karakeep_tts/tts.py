"""Text-to-speech: chunking, OpenAI calls, MP3 concat, ID3 tagging."""
from __future__ import annotations
import datetime
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError

if TYPE_CHECKING:
    from openai import OpenAI


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


def synthesize_article(
    *,
    client: "OpenAI",
    chunks: list[str],
    voice: str,
    model: str,
    instructions: str,
    output_dir: Path,
) -> list[Path]:
    """Synthesize each chunk to MP3 in output_dir. Returns paths in order."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, chunk in enumerate(chunks):
        path = output_dir / f"chunk_{i:03d}.mp3"
        kwargs = dict(model=model, voice=voice, input=chunk, response_format="mp3")
        if model == "gpt-4o-mini-tts":
            kwargs["instructions"] = instructions
        with client.audio.speech.with_streaming_response.create(**kwargs) as response:
            with open(path, "wb") as f:
                for piece in response.iter_bytes():
                    f.write(piece)
        paths.append(path)
    return paths


def concat_mp3s(inputs: list[Path], output: Path) -> None:
    """Concatenate MP3 files via ffmpeg's concat demuxer."""
    if not inputs:
        raise ValueError("No input files to concatenate")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_path = Path(f.name)
        for p in inputs:
            f.write(f"file '{p.absolute()}'\n")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_path), "-c", "copy", str(output)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")
    finally:
        list_path.unlink(missing_ok=True)


def tag_mp3(path: Path, *, title: str) -> None:
    try:
        audio = EasyID3(str(path))
    except ID3NoHeaderError:
        # No existing ID3v2 tag; create an empty one and reopen
        audio = EasyID3()
        audio.save(str(path))
        audio = EasyID3(str(path))
    audio["title"] = title
    audio["date"] = datetime.datetime.now().isoformat()
    audio.save()


def pick_voice(voices: list[str]) -> str:
    if not voices:
        raise ValueError("Voice list is empty")
    return random.choice(voices)
