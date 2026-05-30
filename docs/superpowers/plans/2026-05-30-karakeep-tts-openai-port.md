# karakeep-tts OpenAI + Overcast Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `karakeep-tts` from ElevenLabs to OpenAI TTS, replace Audiobookshelf with Overcast upload as the sink, restructure as a modular Python package, and ship a Docker quick-start.

**Architecture:** Modular package `karakeep_tts/` with `config.py`, `karakeep.py`, `tts.py`, `overcast.py`, `pipeline.py`, `main.py`. Each external system (Karakeep, OpenAI, Overcast) lives in its own module with its own HTTP client and is mock-testable in isolation. The Overcast uploader is a git dependency on a personal fork of `pawelkami/overcast-uploader` (restructured into an importable package).

**Tech Stack:** Python 3.12, `uv` for dependency management, `openai` SDK, `requests`, `html2text`, `mutagen`, `pytest` + `responses` for tests, `ffmpeg` for MP3 concat, Docker multi-stage build.

**Reference:** See `docs/superpowers/specs/2026-05-30-karakeep-tts-openai-port-design.md` for full design rationale.

---

## Task 0: Fork and Repackage overcast-uploader

This is prerequisite setup in a **separate repository**. Produces a git URL + SHA we depend on from this project.

**Files (in a separate `~/Developer/overcast-uploader/` clone):**
- Modify: structure of `pawelkami/overcast-uploader` fork

- [ ] **Step 1: Fork upstream**

```bash
gh auth switch --hostname github.com --user tofagerl
gh repo fork pawelkami/overcast-uploader --clone=false
gh repo clone tofagerl/overcast-uploader ~/Developer/overcast-uploader
cd ~/Developer/overcast-uploader
git checkout -b feat/python-package
```

- [ ] **Step 2: Restructure into a package**

Create `~/Developer/overcast-uploader/overcast_uploader/__init__.py`:

```python
"""Importable wrapper around pawelkami/overcast-uploader's reverse-engineered
Overcast Premium upload flow.

Public API:
    send_file_to_overcast(filepath, email, password, clean=False) -> None
"""
from .uploader import send_file_to_overcast, send_directory_to_overcast

__all__ = ["send_file_to_overcast", "send_directory_to_overcast"]
```

Move `overcast-uploader.py` → `overcast_uploader/uploader.py`:

```bash
mkdir -p overcast_uploader
git mv overcast-uploader.py overcast_uploader/uploader.py
```

Strip the `if __name__ == '__main__':` block from `uploader.py` (the CLI argparse part) — keep only the functions `send_file_to_overcast` and `send_directory_to_overcast`.

- [ ] **Step 3: Add pyproject.toml**

Create `~/Developer/overcast-uploader/pyproject.toml`:

```toml
[project]
name = "overcast-uploader"
version = "0.2.0"
description = "Python package wrapper around the Overcast Premium upload flow (forked from pawelkami/overcast-uploader)"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.28.0",
    "beautifulsoup4>=4.11.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["overcast_uploader*"]
```

- [ ] **Step 4: Verify the package imports cleanly**

```bash
cd ~/Developer/overcast-uploader
uv venv && uv pip install -e .
uv run python -c "from overcast_uploader import send_file_to_overcast; print(send_file_to_overcast)"
```

Expected output: `<function send_file_to_overcast at 0x...>`

- [ ] **Step 5: Commit and push**

```bash
git add overcast_uploader/ pyproject.toml
git rm -f requirements.txt  # superseded by pyproject.toml
git commit -m "feat: restructure as importable Python package

Moves overcast-uploader.py into overcast_uploader/ package with
pyproject.toml so the module can be installed as a git dependency
and the functions imported directly.

Original CLI removed; functions preserved unchanged."
git push -u origin feat/python-package
```

- [ ] **Step 6: Capture the SHA for use in the main project**

```bash
git rev-parse HEAD
```

Record the full SHA. Used in Task 7 as `overcast-uploader @ git+https://github.com/tofagerl/overcast-uploader.git@<SHA>`.

---

## Task 1: Wipe Upstream + Scaffold New Package Structure

**Files:**
- Delete: `main.py`
- Delete: `pyproject.toml` (replaced)
- Delete: `uv.lock` (regenerated)
- Delete: `example.env` (replaced in Task 12)
- Create: `karakeep_tts/__init__.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `.gitignore` additions
- Create: `.python-version` (preserve existing)

- [ ] **Step 1: Confirm we are on the feature branch**

```bash
cd ~/Developer/karakeep-tts
git status
git branch --show-current
```

Expected: clean working tree on `feature/openai-overcast-port`.

- [ ] **Step 2: Remove upstream files we are replacing**

```bash
git rm main.py pyproject.toml uv.lock example.env
```

- [ ] **Step 3: Create the new pyproject.toml**

Create `pyproject.toml` (replace `<OVERCAST_UPLOADER_SHA>` with the SHA from Task 0 Step 6):

```toml
[project]
name = "karakeep-tts"
version = "0.2.0"
description = "Generate audio narrations of Karakeep bookmarks via OpenAI TTS, upload to Overcast."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "openai>=1.0.0",
    "requests>=2.32.0",
    "html2text>=2025.4.15",
    "mutagen>=1.47.0",
    "python-dotenv>=1.1.0",
    "tqdm>=4.67.1",
    "overcast-uploader @ git+https://github.com/tofagerl/overcast-uploader.git@<OVERCAST_UPLOADER_SHA>",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "responses>=0.25",
]

[project.scripts]
karakeep-tts = "karakeep_tts.main:main"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["karakeep_tts*"]
```

- [ ] **Step 4: Create package and test scaffolding**

Create empty `karakeep_tts/__init__.py`:

```python
"""karakeep-tts: Karakeep -> OpenAI TTS -> Overcast pipeline."""
__version__ = "0.2.0"
```

Create empty `tests/__init__.py` (file with no content).

- [ ] **Step 5: Add /media and /.venv to .gitignore**

Append to `.gitignore` (skip lines already present):

```gitignore
.venv/
media/
*.pyc
__pycache__/
.pytest_cache/
```

- [ ] **Step 6: Install dependencies and verify uv resolves**

```bash
uv venv
uv sync
uv run python -c "import karakeep_tts; print(karakeep_tts.__version__)"
```

Expected: `0.2.0`. If `overcast-uploader` git install fails, double-check the SHA from Task 0.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml karakeep_tts/ tests/ .gitignore uv.lock
git commit -m "chore: scaffold karakeep_tts package, remove upstream main.py

Wipes the upstream single-file script and replaces it with a package
skeleton. New pyproject.toml depends on openai, mutagen, overcast-uploader
(git dep on tofagerl fork), and html2text. Drops elevenlabs and rich."
```

---

## Task 2: config.py — Environment Configuration

**Files:**
- Create: `karakeep_tts/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest
from karakeep_tts.config import Config


def test_config_loads_required_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("KARAKEEP_API_KEY", "kk-test")
    monkeypatch.setenv("KARAKEEP_API_HOST", "karakeep.example.com")
    monkeypatch.setenv("OVERCAST_EMAIL", "user@example.com")
    monkeypatch.setenv("OVERCAST_PASSWORD", "secret")
    cfg = Config.from_env()
    assert cfg.openai_api_key == "sk-test"
    assert cfg.karakeep_api_key == "kk-test"
    assert cfg.karakeep_api_host == "karakeep.example.com"
    assert cfg.overcast_email == "user@example.com"
    assert cfg.overcast_password == "secret"


def test_config_defaults(monkeypatch):
    for k in ["OPENAI_API_KEY", "KARAKEEP_API_KEY", "KARAKEEP_API_HOST",
              "OVERCAST_EMAIL", "OVERCAST_PASSWORD"]:
        monkeypatch.setenv(k, "x")
    cfg = Config.from_env()
    assert cfg.bookmark_list_name == "Instapaper"
    assert cfg.media_path.name == "media"
    assert cfg.openai_tts_model == "gpt-4o-mini-tts"
    assert cfg.max_chunk_chars == 3800
    assert cfg.sleep_interval == 60
    assert "alloy" in cfg.openai_tts_voices
    assert len(cfg.openai_tts_voices) == 10


def test_config_voices_comma_split(monkeypatch):
    for k in ["OPENAI_API_KEY", "KARAKEEP_API_KEY", "KARAKEEP_API_HOST",
              "OVERCAST_EMAIL", "OVERCAST_PASSWORD"]:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("OPENAI_TTS_VOICES", "alloy, nova, onyx")
    cfg = Config.from_env()
    assert cfg.openai_tts_voices == ["alloy", "nova", "onyx"]


def test_config_missing_required_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("KARAKEEP_API_KEY", "x")
    monkeypatch.setenv("KARAKEEP_API_HOST", "x")
    monkeypatch.setenv("OVERCAST_EMAIL", "x")
    monkeypatch.setenv("OVERCAST_PASSWORD", "x")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Config.from_env()
```

- [ ] **Step 2: Run the failing tests**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError or ModuleNotFoundError for `karakeep_tts.config`.

- [ ] **Step 3: Implement config.py**

Create `karakeep_tts/config.py`:

```python
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
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/config.py tests/test_config.py
git commit -m "feat(config): add Config dataclass loading from env"
```

---

## Task 3: karakeep.py — Karakeep API Client

**Files:**
- Create: `karakeep_tts/karakeep.py`
- Create: `tests/test_karakeep.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_karakeep.py`:

```python
import pytest
import responses
from karakeep_tts.karakeep import KarakeepClient, Bookmark


@responses.activate
def test_get_list_id_by_name():
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L1", "name": "Other"}, {"id": "L2", "name": "Instapaper"}]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    assert client.get_list_id("Instapaper") == "L2"


@responses.activate
def test_get_list_id_missing_raises():
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L1", "name": "Other"}]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    with pytest.raises(ValueError, match="not found"):
        client.get_list_id("Instapaper")


@responses.activate
def test_get_bookmarks_parses_html_to_text():
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [{
            "id": "B1",
            "content": {
                "title": "Hello",
                "url": "https://example.com/a",
                "htmlContent": "<p>Some <b>body</b> text.</p>",
                "description": "desc",
            },
        }]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert len(bms) == 1
    assert bms[0].id == "B1"
    assert bms[0].title == "Hello"
    assert "Some body text" in bms[0].text


@responses.activate
def test_get_bookmarks_skips_malformed():
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [
            {"id": "B1"},  # malformed
            {"id": "B2", "content": {"title": "T", "url": "u", "htmlContent": "<p>x</p>"}},
        ]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert [b.id for b in bms] == ["B2"]


@responses.activate
def test_delete_from_list():
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.delete(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks/B1",
        json={},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    client.delete_bookmark("Instapaper", "B1")
    assert len(responses.calls) == 2  # list lookup + delete
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_karakeep.py -v
```

Expected: ImportError on `karakeep_tts.karakeep`.

- [ ] **Step 3: Implement karakeep.py**

Create `karakeep_tts/karakeep.py`:

```python
"""Karakeep API client. Wraps the subset of endpoints we need."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

import html2text
import requests

_html2text = html2text.HTML2Text()
_html2text.ignore_links = True
_html2text.ignore_emphasis = True
_html2text.ignore_images = True
_html2text.ignore_tables = True


@dataclass(frozen=True)
class Bookmark:
    id: str
    title: str
    url: str
    text: str
    description: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> "Bookmark | None":
        try:
            content = data["content"]
            title = content.get("title") or content.get("description") or data["id"]
            return cls(
                id=data["id"],
                title=title,
                url=content["url"],
                text=_html2text.handle(content["htmlContent"]),
                description=content.get("description"),
            )
        except (KeyError, TypeError):
            return None


class KarakeepClient:
    def __init__(self, host: str, api_key: str, timeout: int = 600):
        self._base = f"https://{host}/api/v1"
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        self._timeout = timeout
        self._list_cache: dict[str, str] = {}

    def _request(self, path: str, method: str = "GET") -> dict:
        resp = requests.request(
            method, f"{self._base}/{path}",
            headers=self._headers, timeout=self._timeout,
        )
        resp.raise_for_status()
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    def get_list_id(self, name: str) -> str:
        if name in self._list_cache:
            return self._list_cache[name]
        for l in self._request("lists").get("lists", []):
            if l.get("name") == name:
                self._list_cache[name] = l["id"]
                return l["id"]
        raise ValueError(f"Karakeep list not found: {name}")

    def get_bookmarks(self, list_name: str) -> Iterator[Bookmark]:
        list_id = self.get_list_id(list_name)
        data = self._request(f"lists/{list_id}/bookmarks")
        for raw in data.get("bookmarks", []):
            bm = Bookmark.from_api(raw)
            if bm is not None:
                yield bm

    def delete_bookmark(self, list_name: str, bookmark_id: str) -> None:
        list_id = self.get_list_id(list_name)
        self._request(f"lists/{list_id}/bookmarks/{bookmark_id}", method="DELETE")
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_karakeep.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/karakeep.py tests/test_karakeep.py
git commit -m "feat(karakeep): add KarakeepClient with list lookup, fetch, delete

Replaces the original http.client + global functions with a requests-based
client class. Bookmark is now a dataclass parsed via Bookmark.from_api()."
```

---

## Task 4: tts.py — Chunking Logic (Pure Function)

**Files:**
- Create: `karakeep_tts/tts.py` (initial skeleton, chunking only)
- Create: `tests/test_chunking.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_chunking.py`:

```python
import pytest
from karakeep_tts.tts import chunk_text


def test_chunk_short_text_one_chunk():
    text = "Just a sentence."
    chunks = chunk_text(text, max_chars=100)
    assert chunks == ["Just a sentence."]


def test_chunk_splits_on_paragraph_boundary():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text, max_chars=25)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 25
    assert "".join(chunks).replace("\n\n", "") == text.replace("\n\n", "")


def test_chunk_splits_on_sentence_when_paragraph_too_long():
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    chunks = chunk_text(text, max_chars=30)
    assert all(len(c) <= 30 for c in chunks)
    # No mid-word splits: every chunk ends at a word boundary
    for c in chunks:
        assert not c.endswith(" ") or c.rstrip().endswith((".", "!", "?"))


def test_chunk_falls_back_to_word_boundary_on_monster_sentence():
    text = "word " * 100  # 500 chars, no sentence punctuation
    chunks = chunk_text(text, max_chars=50)
    assert all(len(c) <= 50 for c in chunks)
    # No mid-word split
    for c in chunks:
        assert " word" not in c[-5:] or c.endswith("word")


def test_chunk_preserves_all_content():
    text = "Paragraph A.\n\n" + ("Sentence. " * 50) + "\n\nParagraph C."
    chunks = chunk_text(text, max_chars=80)
    joined = " ".join(c.strip() for c in chunks)
    # All meaningful words preserved
    assert joined.count("Sentence.") == 50
    assert "Paragraph A." in joined
    assert "Paragraph C." in joined


def test_chunk_raises_on_unsplittable_giant_word():
    # A single word longer than max_chars
    with pytest.raises(ValueError, match="cannot be split"):
        chunk_text("x" * 1000, max_chars=100)
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement chunk_text**

Create `karakeep_tts/tts.py`:

```python
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
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_chunking.py -v
```

Expected: 6 passed. If any fail, iterate on `chunk_text` — the tests are the contract.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/tts.py tests/test_chunking.py
git commit -m "feat(tts): add chunk_text with paragraph/sentence/word fallback"
```

---

## Task 5: tts.py — OpenAI Synthesis (Mocked)

**Files:**
- Modify: `karakeep_tts/tts.py` (add `synthesize_chunk` and `synthesize_article`)
- Create: `tests/test_tts_openai.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tts_openai.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch
from karakeep_tts.tts import synthesize_article


def test_synthesize_article_calls_openai_per_chunk(tmp_path):
    fake_client = MagicMock()
    # streaming response yields bytes
    fake_response = MagicMock()
    fake_response.iter_bytes.return_value = [b"audio-data"]
    fake_client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value = fake_response

    chunks = ["chunk one", "chunk two", "chunk three"]
    output_dir = tmp_path / "chunks"
    output_dir.mkdir()

    paths = synthesize_article(
        client=fake_client,
        chunks=chunks,
        voice="alloy",
        model="gpt-4o-mini-tts",
        instructions="narrator voice",
        output_dir=output_dir,
    )

    assert len(paths) == 3
    for i, p in enumerate(paths):
        assert p.name == f"chunk_{i:03d}.mp3"
        assert p.read_bytes() == b"audio-data"

    # All chunks use the same voice and model
    calls = fake_client.audio.speech.with_streaming_response.create.call_args_list
    assert len(calls) == 3
    for call in calls:
        assert call.kwargs["voice"] == "alloy"
        assert call.kwargs["model"] == "gpt-4o-mini-tts"
        assert call.kwargs["instructions"] == "narrator voice"


def test_synthesize_article_skips_instructions_for_tts_1(tmp_path):
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.iter_bytes.return_value = [b"x"]
    fake_client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value = fake_response

    synthesize_article(
        client=fake_client,
        chunks=["c"],
        voice="alloy",
        model="tts-1",
        instructions="ignored",
        output_dir=tmp_path,
    )
    call = fake_client.audio.speech.with_streaming_response.create.call_args
    assert "instructions" not in call.kwargs
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_tts_openai.py -v
```

Expected: ImportError for `synthesize_article`.

- [ ] **Step 3: Implement synthesize_article**

Append to `karakeep_tts/tts.py`:

```python
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


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
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_tts_openai.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/tts.py tests/test_tts_openai.py
git commit -m "feat(tts): synthesize_article streams OpenAI TTS per chunk to MP3"
```

---

## Task 6: tts.py — ffmpeg Concat + ID3 Tagging

**Files:**
- Modify: `karakeep_tts/tts.py` (add `concat_mp3s`, `tag_mp3`, `pick_voice`)
- Create: `tests/test_tts_concat.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tts_concat.py`:

```python
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from karakeep_tts.tts import concat_mp3s, tag_mp3, pick_voice


def test_concat_writes_ffmpeg_list_file_and_runs_concat(tmp_path):
    a = tmp_path / "a.mp3"
    b = tmp_path / "b.mp3"
    a.write_bytes(b"a"); b.write_bytes(b"b")
    out = tmp_path / "out.mp3"

    with patch("karakeep_tts.tts.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        concat_mp3s([a, b], out)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "ffmpeg"
        assert "-f" in cmd and "concat" in cmd
        assert "-safe" in cmd and "0" in cmd
        assert "-c" in cmd and "copy" in cmd
        assert str(out) in cmd


def test_concat_raises_on_ffmpeg_failure(tmp_path):
    a = tmp_path / "a.mp3"; a.write_bytes(b"a")
    out = tmp_path / "out.mp3"
    with patch("karakeep_tts.tts.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg error")
        import pytest
        with pytest.raises(RuntimeError, match="ffmpeg"):
            concat_mp3s([a], out)


def test_tag_mp3_sets_title_and_date(tmp_path):
    # Use a real (tiny but valid) MP3 — generate via ffmpeg in a fixture would be heavy.
    # Instead patch EasyID3 to assert it's called correctly.
    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"\xff\xfb" + b"\x00" * 100)  # MPEG sync header + padding
    with patch("karakeep_tts.tts.EasyID3") as mock_easyid3:
        instance = MagicMock()
        mock_easyid3.return_value = instance
        tag_mp3(mp3, title="My Title")
        instance.__setitem__.assert_any_call("title", "My Title")
        # date is also set
        date_calls = [c for c in instance.__setitem__.call_args_list if c.args[0] == "date"]
        assert len(date_calls) == 1
        instance.save.assert_called_once()


def test_pick_voice_returns_one_from_list():
    voices = ["alloy", "nova", "onyx"]
    assert pick_voice(voices) in voices


def test_pick_voice_empty_raises():
    import pytest
    with pytest.raises(ValueError, match="empty"):
        pick_voice([])
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_tts_concat.py -v
```

Expected: ImportError for `concat_mp3s`, `tag_mp3`, `pick_voice`.

- [ ] **Step 3: Implement concat_mp3s, tag_mp3, pick_voice**

Append to `karakeep_tts/tts.py`:

```python
import datetime
import random
import subprocess
import tempfile

from mutagen.easyid3 import EasyID3


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
    audio = EasyID3(str(path))
    audio["title"] = title
    audio["date"] = datetime.datetime.now().isoformat()
    audio.save()


def pick_voice(voices: list[str]) -> str:
    if not voices:
        raise ValueError("Voice list is empty")
    return random.choice(voices)
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_tts_concat.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/tts.py tests/test_tts_concat.py
git commit -m "feat(tts): add ffmpeg concat, ID3 tagging, random voice picker"
```

---

## Task 7: overcast.py — Upload Wrapper

**Files:**
- Create: `karakeep_tts/overcast.py`
- Create: `tests/test_overcast.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_overcast.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from karakeep_tts.overcast import upload_to_overcast


def test_upload_delegates_to_overcast_uploader(tmp_path):
    mp3 = tmp_path / "test.mp3"
    mp3.write_bytes(b"mp3")

    with patch("karakeep_tts.overcast.send_file_to_overcast") as mock_send:
        upload_to_overcast(mp3, email="u@e.com", password="pw")
        mock_send.assert_called_once_with(str(mp3), "u@e.com", "pw")


def test_upload_raises_for_missing_file(tmp_path):
    missing = tmp_path / "nope.mp3"
    with pytest.raises(FileNotFoundError):
        upload_to_overcast(missing, email="u", password="p")


def test_upload_propagates_uploader_errors(tmp_path):
    mp3 = tmp_path / "x.mp3"; mp3.write_bytes(b"x")
    with patch("karakeep_tts.overcast.send_file_to_overcast", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            upload_to_overcast(mp3, email="u", password="p")
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_overcast.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement overcast.py**

Create `karakeep_tts/overcast.py`:

```python
"""Thin wrapper around the overcast-uploader package."""
from __future__ import annotations
from pathlib import Path

from overcast_uploader import send_file_to_overcast


def upload_to_overcast(mp3_path: Path, *, email: str, password: str) -> None:
    """Upload an MP3 to Overcast Premium. Raises if upload fails."""
    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 not found: {mp3_path}")
    send_file_to_overcast(str(mp3_path), email, password)
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_overcast.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/overcast.py tests/test_overcast.py
git commit -m "feat(overcast): thin wrapper around overcast-uploader fork"
```

---

## Task 8: pipeline.py — Per-Bookmark Orchestration

**Files:**
- Create: `karakeep_tts/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pipeline.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from karakeep_tts.pipeline import safe_title, process_bookmark
from karakeep_tts.config import Config
from karakeep_tts.karakeep import Bookmark


def _cfg(tmp_path):
    return Config(
        openai_api_key="x", karakeep_api_key="x", karakeep_api_host="x",
        overcast_email="u", overcast_password="p",
        media_path=tmp_path / "media", bookmark_list_name="Instapaper",
        openai_tts_voices=["alloy"],
    )


def _bm(text="hello world", title="My Article", id="B1"):
    return Bookmark(id=id, title=title, url="https://e.com", text=text)


def test_safe_title_removes_special_chars():
    assert safe_title("Hello, World! 2026") == "Hello_ World_ 2026"


def test_safe_title_falls_back_to_id_for_empty():
    assert safe_title("", fallback="B1") == "B1"
    assert safe_title("///", fallback="B1") == "B1"


def test_safe_title_truncates_to_200():
    assert len(safe_title("x" * 500)) == 200


def test_process_skips_when_uploaded_marker_exists(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.media_path.mkdir(parents=True)
    bm = _bm()
    title = safe_title(bm.title, fallback=bm.id)
    (cfg.media_path / f"{title}.mp3").write_bytes(b"x")
    (cfg.media_path / f"{title}.uploaded").write_text("")

    karakeep = MagicMock()
    openai_client = MagicMock()
    with patch("karakeep_tts.pipeline.synthesize_article") as syn, \
         patch("karakeep_tts.pipeline.concat_mp3s") as cat, \
         patch("karakeep_tts.pipeline.upload_to_overcast") as up:
        process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)
        syn.assert_not_called()
        cat.assert_not_called()
        up.assert_not_called()
        karakeep.delete_bookmark.assert_called_once_with("Instapaper", "B1")


def test_process_full_happy_path(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.media_path.mkdir(parents=True)
    bm = _bm()

    karakeep = MagicMock()
    openai_client = MagicMock()
    with patch("karakeep_tts.pipeline.synthesize_article", return_value=[tmp_path / "c0.mp3"]) as syn, \
         patch("karakeep_tts.pipeline.concat_mp3s") as cat, \
         patch("karakeep_tts.pipeline.tag_mp3") as tag, \
         patch("karakeep_tts.pipeline.upload_to_overcast") as up:
        # concat_mp3s creates the output file
        cat.side_effect = lambda inputs, output: output.write_bytes(b"final")
        process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)

    syn.assert_called_once()
    cat.assert_called_once()
    tag.assert_called_once()
    up.assert_called_once()
    karakeep.delete_bookmark.assert_called_once_with("Instapaper", "B1")

    title = safe_title(bm.title, fallback=bm.id)
    assert (cfg.media_path / f"{title}.mp3").exists()
    assert (cfg.media_path / f"{title}.uploaded").exists()


def test_process_does_not_delete_when_overcast_fails(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.media_path.mkdir(parents=True)
    bm = _bm()
    karakeep = MagicMock()
    openai_client = MagicMock()
    with patch("karakeep_tts.pipeline.synthesize_article", return_value=[tmp_path / "c.mp3"]), \
         patch("karakeep_tts.pipeline.concat_mp3s", side_effect=lambda i, o: o.write_bytes(b"x")), \
         patch("karakeep_tts.pipeline.tag_mp3"), \
         patch("karakeep_tts.pipeline.upload_to_overcast", side_effect=RuntimeError("upload fail")):
        with pytest.raises(RuntimeError, match="upload fail"):
            process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)
    karakeep.delete_bookmark.assert_not_called()
    title = safe_title(bm.title, fallback=bm.id)
    assert (cfg.media_path / f"{title}.mp3").exists()
    assert not (cfg.media_path / f"{title}.uploaded").exists()


def test_process_does_not_delete_when_tts_fails(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.media_path.mkdir(parents=True)
    bm = _bm()
    karakeep = MagicMock()
    openai_client = MagicMock()
    with patch("karakeep_tts.pipeline.synthesize_article", side_effect=RuntimeError("tts fail")), \
         patch("karakeep_tts.pipeline.upload_to_overcast") as up:
        with pytest.raises(RuntimeError, match="tts fail"):
            process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)
    up.assert_not_called()
    karakeep.delete_bookmark.assert_not_called()
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement pipeline.py**

Create `karakeep_tts/pipeline.py`:

```python
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
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add karakeep_tts/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): per-bookmark orchestration with idempotent skip-if-done"
```

---

## Task 9: main.py — Loop, Healthcheck, Signal Handling

**Files:**
- Create: `karakeep_tts/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_main.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
import requests
from karakeep_tts.main import ping_healthcheck


def test_ping_healthcheck_no_url_is_noop():
    # Should not raise, should not call requests
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("")
        mock_get.assert_not_called()


def test_ping_healthcheck_success_url():
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("https://hc.example.com/abc")
        mock_get.assert_called_once_with("https://hc.example.com/abc", timeout=10)


def test_ping_healthcheck_failure_appends_fail():
    with patch("karakeep_tts.main.requests.get") as mock_get:
        ping_healthcheck("https://hc.example.com/abc/", failure=True)
        mock_get.assert_called_once_with("https://hc.example.com/abc/fail", timeout=10)


def test_ping_healthcheck_swallows_request_errors():
    with patch("karakeep_tts.main.requests.get", side_effect=requests.RequestException("net err")):
        # must not raise
        ping_healthcheck("https://hc.example.com/abc")
```

- [ ] **Step 2: Run failing tests**

```bash
uv run pytest tests/test_main.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement main.py**

Create `karakeep_tts/main.py`:

```python
"""Entrypoint: poll Karakeep, process bookmarks, ping healthcheck, sleep, repeat."""
from __future__ import annotations
import logging
import signal
import sys
import time

import requests
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

from karakeep_tts.config import Config
from karakeep_tts.karakeep import KarakeepClient
from karakeep_tts.pipeline import process_bookmark

log = logging.getLogger("karakeep_tts")


def ping_healthcheck(url: str, failure: bool = False) -> None:
    if not url:
        return
    target = url.rstrip("/") + "/fail" if failure else url
    try:
        requests.get(target, timeout=10)
    except requests.RequestException as exc:
        log.warning("Healthcheck ping failed: %s", exc)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _install_signal_handlers() -> None:
    def _shutdown(signum, _frame):
        log.info("Received signal %s, exiting cleanly", signum)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)


def main() -> None:
    load_dotenv()
    _setup_logging()
    _install_signal_handlers()
    cfg = Config.from_env()
    karakeep = KarakeepClient(host=cfg.karakeep_api_host, api_key=cfg.karakeep_api_key)
    # max_retries=3 covers the spec's "exponential backoff up to 3 retries per chunk"
    # for OpenAI 429/5xx (the SDK handles backoff internally).
    openai_client = OpenAI(api_key=cfg.openai_api_key, max_retries=3)

    log.info("Starting karakeep-tts loop, watching list %r every %ds",
             cfg.bookmark_list_name, cfg.sleep_interval)

    while True:
        try:
            bookmarks = list(karakeep.get_bookmarks(cfg.bookmark_list_name))
            for bm in tqdm(bookmarks, disable=not sys.stdout.isatty()):
                try:
                    process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)
                except Exception as exc:
                    log.error("Failed to process bookmark %s (%s): %s", bm.id, bm.title, exc)
            ping_healthcheck(cfg.healthcheck_url)
        except Exception as exc:
            log.exception("Loop iteration failed: %s", exc)
            ping_healthcheck(cfg.healthcheck_url, failure=True)
        time.sleep(cfg.sleep_interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests until green**

```bash
uv run pytest tests/test_main.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass across config, karakeep, chunking, tts_openai, tts_concat, overcast, pipeline, main.

- [ ] **Step 6: Commit**

```bash
git add karakeep_tts/main.py tests/test_main.py
git commit -m "feat(main): entrypoint with polling loop, healthcheck, signal handling"
```

---

## Task 10: Dockerfile + docker-compose.yml

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create .dockerignore**

Create `.dockerignore`:

```
.git/
.venv/
media/
__pycache__/
*.pyc
.pytest_cache/
docs/
tests/
.env
```

- [ ] **Step 2: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# git is needed to install overcast-uploader from a git source
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Create the venv with all deps (no source yet, so this layer is cached)
RUN uv sync --frozen --no-install-project

COPY karakeep_tts/ ./karakeep_tts/
RUN uv sync --frozen

# --- runtime stage ---
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/karakeep_tts /app/karakeep_tts

ENV PATH="/app/.venv/bin:${PATH}"
ENV MEDIA_PATH=/data/media

USER app
VOLUME ["/data/media"]

ENTRYPOINT ["python", "-m", "karakeep_tts.main"]
```

- [ ] **Step 3: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  karakeep-tts:
    build: .
    image: karakeep-tts:latest
    restart: unless-stopped
    environment:
      # Required
      OPENAI_API_KEY: ${OPENAI_API_KEY:?required}
      KARAKEEP_API_KEY: ${KARAKEEP_API_KEY:?required}
      KARAKEEP_API_HOST: ${KARAKEEP_API_HOST:?required}
      OVERCAST_EMAIL: ${OVERCAST_EMAIL:?required}
      OVERCAST_PASSWORD: ${OVERCAST_PASSWORD:?required}
      # Optional
      BOOKMARK_LIST_NAME: ${BOOKMARK_LIST_NAME:-Instapaper}
      OPENAI_TTS_MODEL: ${OPENAI_TTS_MODEL:-gpt-4o-mini-tts}
      OPENAI_TTS_VOICES: ${OPENAI_TTS_VOICES:-}
      OPENAI_TTS_INSTRUCTIONS: ${OPENAI_TTS_INSTRUCTIONS:-}
      MAX_CHUNK_CHARS: ${MAX_CHUNK_CHARS:-3800}
      SLEEP_INTERVAL: ${SLEEP_INTERVAL:-60}
      HEALTHCHECK_URL: ${HEALTHCHECK_URL:-}
    volumes:
      - ./media:/data/media
```

- [ ] **Step 4: Build the image**

```bash
cd ~/Developer/karakeep-tts
docker build -t karakeep-tts:test .
```

Expected: build completes, final image tagged. If the git+https overcast-uploader install fails, the SHA in `pyproject.toml` is wrong or unreachable.

- [ ] **Step 5: Verify the container starts and exits on missing env**

```bash
docker run --rm karakeep-tts:test 2>&1 | head -20
```

Expected: a `ValueError: Missing required env vars: OPENAI_API_KEY, ...` traceback. (It will exit because env vars aren't set — that's the right behavior.)

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat(docker): multi-stage Dockerfile + compose with media volume"
```

---

## Task 11: example.env and README

**Files:**
- Create: `example.env`
- Modify: `README.md` (full rewrite)

- [ ] **Step 1: Create example.env**

Create `example.env`:

```env
# Required
OPENAI_API_KEY=sk-...
KARAKEEP_API_KEY=...
KARAKEEP_API_HOST=karakeep.example.com
OVERCAST_EMAIL=you@example.com
OVERCAST_PASSWORD=your-overcast-password

# Optional — defaults shown
BOOKMARK_LIST_NAME=Instapaper
MEDIA_PATH=media
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICES=alloy,ash,ballad,coral,echo,fable,nova,onyx,sage,shimmer
OPENAI_TTS_INSTRUCTIONS=Read in a clear, natural narrator voice.
MAX_CHUNK_CHARS=3800
SLEEP_INTERVAL=60
HEALTHCHECK_URL=
```

- [ ] **Step 2: Rewrite README.md**

Replace `README.md` entirely:

````markdown
# karakeep-tts

Watch a [Karakeep](https://karakeep.app/) bookmark list, narrate each new bookmark with **OpenAI's TTS**, upload the resulting MP3 to **Overcast Premium**, and remove the bookmark from the list. The MP3 is also retained locally as a backup.

Forked from [samanthavbarron/karakeep-tts](https://github.com/samanthavbarron/karakeep-tts), which uses ElevenLabs + local files for Audiobookshelf. This fork swaps to OpenAI TTS and uploads to Overcast instead.

## Quick start (Docker)

```bash
cp example.env .env
$EDITOR .env   # fill in API keys + Overcast credentials
docker compose up -d --build
docker compose logs -f
```

That's it. Drop a bookmark into your `Instapaper` Karakeep list and within `SLEEP_INTERVAL` seconds it will show up in Overcast Uploads.

## How it works

1. Poll the configured Karakeep list every `SLEEP_INTERVAL` seconds.
2. For each bookmark: HTML → text → chunked to fit OpenAI's 4096-char per-request limit.
3. Each chunk → OpenAI TTS (default `gpt-4o-mini-tts`) using a randomly-picked voice (same voice across all chunks of one article).
4. Chunks concatenated with `ffmpeg`, ID3 tagged, uploaded to Overcast via [tofagerl/overcast-uploader](https://github.com/tofagerl/overcast-uploader) (forked from [pawelkami/overcast-uploader](https://github.com/pawelkami/overcast-uploader)).
5. On successful upload, the bookmark is deleted from the Karakeep list.

Pipeline is **idempotent**: if a process crashes between TTS and upload, the next loop resumes from upload (skipping TTS) using `.uploaded` marker files alongside each MP3.

## Environment variables

| Variable | Default | Required | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | — | Yes | |
| `KARAKEEP_API_KEY` | — | Yes | |
| `KARAKEEP_API_HOST` | — | Yes | e.g. `karakeep.example.com` |
| `OVERCAST_EMAIL` | — | Yes | Overcast Premium account email |
| `OVERCAST_PASSWORD` | — | Yes | Account password (no 2FA support) |
| `BOOKMARK_LIST_NAME` | `Instapaper` | No | Karakeep list to watch |
| `MEDIA_PATH` | `media` | No | Local MP3 backup folder |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | No | Or `tts-1`, `tts-1-hd` |
| `OPENAI_TTS_VOICES` | (all 10 voices) | No | Comma-separated list to randomize from |
| `OPENAI_TTS_INSTRUCTIONS` | "Read in a clear, natural narrator voice." | No | Only used by `gpt-4o-mini-tts` |
| `MAX_CHUNK_CHARS` | `3800` | No | Headroom under OpenAI's 4096 hard limit |
| `SLEEP_INTERVAL` | `60` | No | Seconds between Karakeep polls |
| `HEALTHCHECK_URL` | — | No | Healthchecks.io-style ping URL |

## Manual smoke test

After `docker compose up`, drop a short article (one paragraph) into your `Instapaper` Karakeep list. Within `SLEEP_INTERVAL` seconds:

- Logs should show `Failed to process` if anything went wrong — read carefully
- `./media/` should contain `<title>.mp3` + `<title>.uploaded`
- Overcast Uploads tab at https://overcast.fm/uploads should list the file
- The bookmark should be gone from the Karakeep list

## Local development

```bash
uv sync
uv run pytest -v
uv run python -m karakeep_tts.main   # needs .env populated
```

## License

MIT — same as upstream.
````

- [ ] **Step 3: Commit**

```bash
git add example.env README.md
git commit -m "docs: rewrite README, add example.env for OpenAI+Overcast flow"
```

---

## Task 12: Final Verification + Push

- [ ] **Step 1: Run full test suite**

```bash
cd ~/Developer/karakeep-tts
uv run pytest -v
```

Expected: all tests pass (config: 4, karakeep: 5, chunking: 6, tts_openai: 2, tts_concat: 5, overcast: 3, pipeline: 7, main: 4 — total 36 tests).

- [ ] **Step 2: Build Docker image one more time end-to-end**

```bash
docker build -t karakeep-tts:final .
```

Expected: clean build.

- [ ] **Step 3: Push to the fork**

```bash
git push -u origin feature/openai-overcast-port
```

- [ ] **Step 4: Open a draft PR against upstream (optional)**

Note: since this is a personal fork on `tofagerl/karakeep-tts`, the PR would target `tofagerl/main`, not the upstream `samanthavbarron`. Skip if you intend the fork to stay diverged.

```bash
gh pr create --draft --title "Port to OpenAI TTS + Overcast + Docker" \
  --body "$(cat docs/superpowers/specs/2026-05-30-karakeep-tts-openai-port-design.md | head -30)"
```

- [ ] **Step 5: Manual end-to-end smoke test**

Populate `.env` with real credentials, run `docker compose up`, drop a short test article into the `Instapaper` Karakeep list, verify:
- Logs show successful processing
- `./media/` contains the MP3 + `.uploaded` marker
- Overcast Uploads page shows the file
- Karakeep list no longer contains the bookmark

If anything fails, the relevant module's tests should be extended to cover the failure case before fixing.
