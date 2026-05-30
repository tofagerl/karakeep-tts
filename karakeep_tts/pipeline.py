"""Per-bookmark orchestration. Idempotent: safe to re-run on partial failure."""
from __future__ import annotations
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from karakeep_tts.config import Config
from karakeep_tts.karakeep import Bookmark, KarakeepClient
from karakeep_tts.tts import (
    chunk_text, concat_mp3s, pick_voice, synthesize_article, tag_mp3,
)
from karakeep_tts.overcast import upload_to_overcast

if TYPE_CHECKING:
    from openai import OpenAI

_SAFE_RE = re.compile(r"[^A-Za-z0-9 _-]")


def safe_title(title: str, fallback: str = "untitled") -> str:
    """Make a string safe for use as a filename. Falls back if title empty."""
    cleaned = _SAFE_RE.sub("_", title).strip()
    if not cleaned or not re.search(r"[A-Za-z0-9]", cleaned):
        return fallback
    return cleaned[:200]


def _wrap_with_preamble(bm: Bookmark) -> str:
    pre = f"The following article is titled {bm.title}. This is read by an automated voice."
    post = f"This article was titled {bm.title}. Thanks for listening!"
    return f"{pre}\n\n{bm.text}\n\n{post}"


def process_bookmark(
    bm: Bookmark,
    *,
    cfg: Config,
    karakeep: KarakeepClient,
    openai_client: "OpenAI",
) -> None:
    """Run the full pipeline for one bookmark.

    Idempotent: if MP3 + .uploaded marker exist, skip straight to Karakeep delete.
    On any pre-upload failure, raises without deleting from Karakeep.
    On upload failure, raises without creating the marker.
    """
    title = safe_title(bm.title, fallback=bm.id)
    mp3_path = cfg.media_path / f"{title}.mp3"
    marker_path = cfg.media_path / f"{title}.uploaded"
    cfg.media_path.mkdir(parents=True, exist_ok=True)

    if mp3_path.exists() and marker_path.exists():
        karakeep.delete_bookmark(cfg.bookmark_list_name, bm.id)
        return

    if not mp3_path.exists():
        chunks = chunk_text(_wrap_with_preamble(bm), max_chars=cfg.max_chunk_chars)
        voice = pick_voice(cfg.openai_tts_voices)
        with tempfile.TemporaryDirectory(prefix=f"karakeep_tts_{title}_") as tmp:
            chunk_paths = synthesize_article(
                client=openai_client,
                chunks=chunks,
                voice=voice,
                model=cfg.openai_tts_model,
                instructions=cfg.openai_tts_instructions,
                output_dir=Path(tmp),
            )
            concat_mp3s(chunk_paths, mp3_path)
        tag_mp3(mp3_path, title=bm.title)

    upload_to_overcast(mp3_path, email=cfg.overcast_email, password=cfg.overcast_password)
    marker_path.write_text("")
    karakeep.delete_bookmark(cfg.bookmark_list_name, bm.id)
