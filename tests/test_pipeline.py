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
