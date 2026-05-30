# karakeep-tts — Port to OpenAI TTS + Overcast + Docker

**Date:** 2026-05-30
**Status:** Draft for review
**Upstream:** [samanthavbarron/karakeep-tts](https://github.com/samanthavbarron/karakeep-tts)

## Goal

Port the existing `karakeep-tts` script to:

1. Use **OpenAI's TTS API** instead of ElevenLabs.
2. Upload generated MP3s to **Overcast** (Marco Arment's podcast app) as the primary listening target.
3. Run as a **Docker container** with a single `docker compose up` quick-start.
4. Watch a Karakeep list called **Instapaper** (replacing the old default `Podcast`).

The new flow per bookmark: Karakeep → text → OpenAI TTS (chunked, concatenated) → MP3 with ID3 tags → Overcast upload → remove from Karakeep list. The local MP3 is retained in a media folder as a backup.

## Non-Goals

- Audiobookshelf integration (dropped — Overcast becomes the sole sink).
- Backwards compatibility with the original script's env var names. Renames are deliberate; no upgrade path is provided.
- A plugin/sink-abstraction architecture. Overcast is the only sink; if more are wanted later, refactor at that point.
- Live integration tests against OpenAI, Karakeep, or Overcast (cost + flake).

## Architecture

```
karakeep_tts/
├── config.py        # env var loading, Config dataclass
├── karakeep.py      # Karakeep API client (list lookup, fetch bookmarks, delete)
├── tts.py           # text chunking, OpenAI TTS calls, ffmpeg concat, ID3 tagging
├── overcast.py      # thin wrapper around overcast-uploader fork (git dep)
├── pipeline.py      # per-bookmark orchestration + idempotency
└── main.py          # loop, sleep, healthcheck, signal handling
tests/
├── test_chunking.py
├── test_pipeline.py
└── test_overcast.py
Dockerfile
docker-compose.yml
pyproject.toml
README.md
example.env
```

**Dependency direction:** `main` → `pipeline` → `{karakeep, tts, overcast}` → `config`. The three external-system modules have no cross-dependencies, each owns its HTTP client, and each is testable in isolation.

**Rationale:** the three external systems (Karakeep, OpenAI, Overcast) each have their own auth, error modes, and likely-future-breakage. Isolation means an Overcast HTML change does not touch TTS code, and each module can be tested with mocked HTTP without the others.

## Per-Bookmark Pipeline

1. **Fetch** bookmark from the configured Karakeep list. Convert `htmlContent` → text via `html2text` (carried over from the original).
2. **Skip-if-done check:** if `media/{safe_title}.mp3` exists *and* a sibling `media/{safe_title}.uploaded` marker file exists, skip to step 7. Makes the pipeline crash-safe — if Overcast was down on the previous run, we do not redo TTS. `safe_title` is the bookmark title with characters outside `[A-Za-z0-9 _-]` replaced by `_` and trimmed to 200 chars. If the title is empty, fall back to the bookmark `id`.
3. **Chunk** the text into pieces ≤ `MAX_CHUNK_CHARS` (default 3800, leaving headroom under OpenAI's 4096-char hard limit). Split on paragraph boundaries first; fall back to sentence boundaries if a single paragraph is too large; final fallback is word boundaries. The preamble is prepended to the first chunk and the postamble is appended to the last chunk (so a single-chunk article gets both, wrapping the body).
4. **Pick voice once per article** — uniform random from `OPENAI_TTS_VOICES`. The same voice is used across all chunks of one article so the narrator does not switch mid-stream.
5. **TTS each chunk:** call OpenAI `audio.speech.create` with `OPENAI_TTS_MODEL` (default `gpt-4o-mini-tts`). For `gpt-4o-mini-tts`, pass `OPENAI_TTS_INSTRUCTIONS` to set tone. Write each chunk MP3 into a per-article temp subdir.
6. **Concatenate** chunks via `ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp3` to produce the final MP3. Write ID3 tags (`title`, `date`). Delete the chunk temp dir.
7. **Upload to Overcast** via the vendored fork (see "Overcast dependency" below). On success, create `media/{safe_title}.uploaded` marker file.
8. **Remove the bookmark from the Karakeep list.** Only happens if steps 6 and 7 both succeeded. On any earlier failure, leave the bookmark in place; the next loop iteration retries.

## Failure Handling

| Failure | Behavior |
|---|---|
| OpenAI 429 / 5xx on a chunk | Exponential backoff up to 3 retries per chunk; then skip the article, log error |
| `ffmpeg` concat failure | Log, leave chunk files in temp dir for debugging, skip article |
| Overcast upload failure | Log, keep MP3, do not create `.uploaded` marker, do not delete from Karakeep. Step 2 of next loop skips TTS and retries upload |
| Karakeep delete failure | Log; `.uploaded` marker stays so we do not re-upload. Next loop retries the delete |
| Karakeep list-fetch failure | Log, skip the loop iteration, ping healthcheck `/fail`, sleep, try again |
| OpenAI auth/quota error | Log, skip article, ping healthcheck `/fail` (this is a config problem) |

**Why filesystem markers rather than a JSON state file or DB:** keeps the design stateless and easy to inspect; aligns with the original's filesystem-as-state approach (`if not self.path().exists()`).

## Overcast Dependency

No official Overcast upload API exists. The only practical Python library is [`pawelkami/overcast-uploader`](https://github.com/pawelkami/overcast-uploader), which is a single CLI script (not on PyPI, last commit 2023-11-13) that reverse-engineers the Overcast Premium web upload form.

**Plan:** fork `pawelkami/overcast-uploader` to `tofagerl/overcast-uploader`, restructure into a proper importable package (`overcast_uploader/__init__.py` exposing `send_file_to_overcast(path, email, password)`), add minimal `pyproject.toml`, and depend on it from this project as a git dependency pinned to a commit SHA:

```toml
dependencies = [
    "overcast-uploader @ git+https://github.com/tofagerl/overcast-uploader.git@<sha>",
]
```

`overcast.py` is then a thin wrapper that imports `send_file_to_overcast` and handles credential injection + retries. When (not if) Overcast's form changes, the fix is a single commit in the fork plus a SHA bump here.

## Configuration

| Env var | Default | Required | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | — | Yes | Replaces `ELEVENLABS_API_KEY` |
| `KARAKEEP_API_KEY` | — | Yes | Unchanged from upstream |
| `KARAKEEP_API_HOST` | — | Yes | Unchanged from upstream |
| `OVERCAST_EMAIL` | — | Yes | New |
| `OVERCAST_PASSWORD` | — | Yes | New |
| `BOOKMARK_LIST_NAME` | `Instapaper` | No | Default changed from `Podcast` |
| `MEDIA_PATH` | `media` | No | Unchanged from upstream |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | No | Replaces `ELEVENLABS_MODEL_ID` |
| `OPENAI_TTS_VOICES` | `alloy,ash,ballad,coral,echo,fable,nova,onyx,sage,shimmer` | No | Comma-separated whitelist randomized per article |
| `OPENAI_TTS_INSTRUCTIONS` | `Read in a clear, natural narrator voice.` | No | Only used when model is `gpt-4o-mini-tts` |
| `MAX_CHUNK_CHARS` | `3800` | No | Headroom under OpenAI's 4096 limit |
| `SLEEP_INTERVAL` | `60` | No | Unchanged from upstream |
| `HEALTHCHECK_URL` | — | No | Unchanged from upstream |

Renames are intentional. Upstream's script was never packaged, so no users need an upgrade path.

## Docker

- **Base image:** `python:3.12-slim` with `ffmpeg` apt-installed (~80MB extra, but the only reliable cross-platform MP3 concat path).
- **Multi-stage build:**
  - Stage 1: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` resolves and installs deps into a venv. `git` is required in this stage for the Overcast git dependency.
  - Stage 2: slim runtime, copies the venv and source from stage 1.
- **Volume:** `/data/media` mounted from host for MP3 backups.
- **User:** runs as non-root (`uid=1000`).
- **Healthcheck:** uses the existing `HEALTHCHECK_URL` ping (compatible with healthchecks.io etc.); no Docker `HEALTHCHECK` directive.
- **`docker-compose.yml`:** included as a quick-start template with all env vars and the volume mount.

## Testing

| Test file | What it covers |
|---|---|
| `test_chunking.py` | Variety of inputs (short, paragraph-heavy, sentence-heavy, single-monster-paragraph). Asserts every chunk ≤ `MAX_CHUNK_CHARS`, no mid-word splits, no content loss when chunks are rejoined |
| `test_pipeline.py` | Mocks `karakeep`, `tts`, `overcast` modules. Verifies idempotency (skip when both MP3 and marker exist), and the three failure-mode invariants: TTS-fail → no Karakeep delete; Overcast-fail → no Karakeep delete; both-ok → Karakeep delete called |
| `test_overcast.py` | Mocks `requests` (via `responses`). Verifies the call sequence: login POST → upload-form GET → S3 POST → success-notify POST. Login failure raises rather than silently continuing |

No live integration tests. A manual smoke-test procedure is documented in the README (one tiny test bookmark, run once, verify Overcast received it).

## Dependencies

```toml
dependencies = [
    "openai>=1.0.0",
    "requests>=2.32.0",
    "html2text>=2025.4.15",
    "mutagen>=1.47.0",
    "python-dotenv>=1.1.0",
    "tqdm>=4.67.1",
    "overcast-uploader @ git+https://github.com/tofagerl/overcast-uploader.git@<sha>",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "responses>=0.25",
]
```

Removed from upstream: `elevenlabs`, `rich` (unused), `requests` is moved to a direct dep since the original used `http.client` for Karakeep — we standardize on `requests`. `ffmpeg` is a system dep, installed in the Docker image.

## Open Questions / Out of Scope

- **Overcast 2FA:** confirmed not enabled — clean email+password login. The unofficial upload flow will work.
- **Multi-list watching:** not in scope (single list only, per current decision).
- **Audio post-processing** (normalization, silence trimming between chunks): not in scope; revisit if quality issues appear.
