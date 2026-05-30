"""Environment-driven configuration."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_VOICES = ["alloy", "ash", "ballad", "coral", "echo",
                  "fable", "nova", "onyx", "sage", "shimmer"]
DEFAULT_INSTRUCTIONS = "Read in a clear, natural narrator voice."

REQUIRED = ["OPENAI_API_KEY", "KARAKEEP_API_KEY", "KARAKEEP_API_HOST",
            "OVERCAST_EMAIL", "OVERCAST_PASSWORD"]


@dataclass(frozen=True)
class Config:
    openai_api_key: str
    karakeep_api_key: str
    karakeep_api_host: str
    overcast_email: str
    overcast_password: str
    media_path: Path = Path("media")
    bookmark_list_name: str = "Instapaper"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voices: list[str] = field(default_factory=lambda: list(DEFAULT_VOICES))
    openai_tts_instructions: str = DEFAULT_INSTRUCTIONS
    max_chunk_chars: int = 3800
    sleep_interval: int = 60
    healthcheck_url: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        missing = [k for k in REQUIRED if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")
        voices_raw = os.getenv("OPENAI_TTS_VOICES", ",".join(DEFAULT_VOICES))
        voices = [v.strip() for v in voices_raw.split(",") if v.strip()]
        return cls(
            openai_api_key=os.environ["OPENAI_API_KEY"],
            karakeep_api_key=os.environ["KARAKEEP_API_KEY"],
            karakeep_api_host=os.environ["KARAKEEP_API_HOST"],
            overcast_email=os.environ["OVERCAST_EMAIL"],
            overcast_password=os.environ["OVERCAST_PASSWORD"],
            media_path=Path(os.getenv("MEDIA_PATH", "media")),
            bookmark_list_name=os.getenv("BOOKMARK_LIST_NAME", "Instapaper"),
            openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            openai_tts_voices=voices,
            openai_tts_instructions=os.getenv("OPENAI_TTS_INSTRUCTIONS", DEFAULT_INSTRUCTIONS),
            max_chunk_chars=int(os.getenv("MAX_CHUNK_CHARS", "3800")),
            sleep_interval=int(os.getenv("SLEEP_INTERVAL", "60")),
            healthcheck_url=os.getenv("HEALTHCHECK_URL", ""),
        )
