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
| `MEDIA_PATH` | `media` (Docker: `/data/media`) | No | Local MP3 backup folder. In Docker, mounted from `./media` on host. |
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
