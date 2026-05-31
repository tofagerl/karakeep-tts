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
                "type": "link",
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
            {"id": "B2", "content": {"type": "link", "title": "T", "url": "u",
                                     "htmlContent": "<p>x</p>"}},
        ]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert [b.id for b in bms] == ["B2"]


@responses.activate
def test_get_bookmarks_skips_when_htmlcontent_is_null():
    """Karakeep returns htmlContent=null for unscraped or non-article bookmarks
    (e.g. YouTube). Must be skipped, not crashed on."""
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [
            {"id": "B1", "content": {"type": "link", "title": "Unscraped",
                                     "url": "https://example.com", "htmlContent": None}},
            {"id": "B2", "content": {"type": "link", "title": "OK",
                                     "url": "https://example.com/b",
                                     "htmlContent": "<p>body</p>"}},
            {"id": "B3", "content": {"type": "link", "title": "NoUrl", "url": None,
                                     "htmlContent": "<p>x</p>"}},
        ]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert [b.id for b in bms] == ["B2"]


@responses.activate
def test_get_bookmarks_continues_past_individual_parse_failure(monkeypatch):
    """A bookmark that raises inside from_api must not poison the whole iteration."""
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [
            {"id": "BAD"},
            {"id": "B2", "content": {"type": "link", "title": "OK", "url": "u",
                                     "htmlContent": "<p>x</p>"}},
        ]},
    )
    # Force from_api to raise on the first bookmark
    original = Bookmark.from_api
    def flaky(data):
        if data.get("id") == "BAD":
            raise RuntimeError("boom")
        return original(data)
    monkeypatch.setattr(Bookmark, "from_api", staticmethod(flaky))

    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert [b.id for b in bms] == ["B2"]


@responses.activate
def test_get_bookmarks_uses_text_field_for_text_type_bookmarks():
    """For type=text bookmarks, use content.text directly; no html2text needed."""
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [{
            "id": "T1",
            "title": "My Note",
            "content": {
                "type": "text",
                "text": "This is a plain text note. No HTML at all.",
                "sourceUrl": "https://origin.example.com",
            },
        }]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert len(bms) == 1
    assert bms[0].id == "T1"
    assert bms[0].title == "My Note"
    assert bms[0].text == "This is a plain text note. No HTML at all."
    assert bms[0].url == "https://origin.example.com"


@responses.activate
def test_get_bookmarks_skips_unsupported_content_types():
    """Asset (PDF/image) and unknown bookmark types aren't supported for TTS."""
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [
            {"id": "A1", "content": {"type": "asset", "assetType": "pdf", "assetId": "x"}},
            {"id": "U1", "content": {"type": "unknown"}},
            {"id": "L1", "content": {"type": "link", "url": "u",
                                     "htmlContent": "<p>ok</p>"}},
        ]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert [b.id for b in bms] == ["L1"]


@responses.activate
def test_get_bookmarks_uses_bookmark_level_title_when_present():
    """The bookmark-level title (user-overridable) wins over content.title."""
    responses.get(
        "https://karakeep.example.com/api/v1/lists",
        json={"lists": [{"id": "L2", "name": "Instapaper"}]},
    )
    responses.get(
        "https://karakeep.example.com/api/v1/lists/L2/bookmarks",
        json={"bookmarks": [{
            "id": "B1",
            "title": "User Override",
            "content": {
                "type": "link",
                "url": "https://example.com",
                "title": "Scraped Title",
                "htmlContent": "<p>x</p>",
            },
        }]},
    )
    client = KarakeepClient(host="karakeep.example.com", api_key="k")
    bms = list(client.get_bookmarks("Instapaper"))
    assert bms[0].title == "User Override"


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
