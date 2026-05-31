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
            log.info("Found %d processable bookmark(s) in %r", len(bookmarks), cfg.bookmark_list_name)
            for bm in tqdm(bookmarks, disable=not sys.stdout.isatty()):
                try:
                    process_bookmark(bm, cfg=cfg, karakeep=karakeep, openai_client=openai_client)
                except Exception as exc:
                    log.error("Failed to process bookmark %s (%s): %s", bm.id, bm.title, exc)
            ping_healthcheck(cfg.healthcheck_url)
            log.info("Loop iteration complete; sleeping %ds", cfg.sleep_interval)
        except Exception as exc:
            log.exception("Loop iteration failed: %s", exc)
            ping_healthcheck(cfg.healthcheck_url, failure=True)
        time.sleep(cfg.sleep_interval)


if __name__ == "__main__":
    main()
