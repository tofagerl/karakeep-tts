"""Karakeep API client. Wraps the subset of endpoints we need."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Iterator

import html2text
import requests

log = logging.getLogger(__name__)

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
        bm_id = data.get("id", "?")
        try:
            content = data.get("content")
            if not isinstance(content, dict):
                log.info("Skipping %s: content field is %r", bm_id, content)
                return None

            content_type = content.get("type")
            if content_type == "link":
                html = content.get("htmlContent")
                url = content.get("url")
                if not html or not url:
                    crawl_status = content.get("crawlStatus")
                    log.info("Skipping link %s: not yet crawled (crawlStatus=%r, htmlContent=%s)",
                             bm_id, crawl_status, "present" if html else "null")
                    return None
                body = _html2text.handle(html)
            elif content_type == "text":
                body = content.get("text")
                url = content.get("sourceUrl") or ""
                if not body:
                    log.info("Skipping text bookmark %s: empty text field", bm_id)
                    return None
            else:
                # asset (pdf/image) and unknown not supported for TTS
                log.info("Skipping %s: unsupported content type %r", bm_id, content_type)
                return None

            # Bookmark-level title wins (user can override); fall back to content's title.
            title = (
                data.get("title")
                or content.get("title")
                or content.get("description")
                or bm_id
            )
            return cls(
                id=data["id"],
                title=title,
                url=url,
                text=body,
                description=content.get("description"),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            log.warning("Skipping %s: parse error %s", bm_id, exc)
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
        # Karakeep 0.30.0+ defaults includeContent=false; we need it true for htmlContent/text.
        data = self._request(f"lists/{list_id}/bookmarks?includeContent=true")
        for raw in data.get("bookmarks", []):
            try:
                bm = Bookmark.from_api(raw)
            except Exception as exc:
                log.warning("Skipping malformed bookmark %s: %s", raw.get("id"), exc)
                continue
            if bm is not None:
                yield bm

    def delete_bookmark(self, list_name: str, bookmark_id: str) -> None:
        list_id = self.get_list_id(list_name)
        self._request(f"lists/{list_id}/bookmarks/{bookmark_id}", method="DELETE")
