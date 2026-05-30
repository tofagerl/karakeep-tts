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
