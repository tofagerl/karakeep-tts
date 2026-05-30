"""Thin wrapper around the overcast-uploader package."""
from __future__ import annotations
from pathlib import Path

from overcast_uploader import send_file_to_overcast


def upload_to_overcast(mp3_path: Path, *, email: str, password: str) -> None:
    """Upload an MP3 to Overcast Premium. Raises if upload fails."""
    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 not found: {mp3_path}")
    send_file_to_overcast(str(mp3_path), email, password)
