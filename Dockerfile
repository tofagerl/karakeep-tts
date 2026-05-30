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
