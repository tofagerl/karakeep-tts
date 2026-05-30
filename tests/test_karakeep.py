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
