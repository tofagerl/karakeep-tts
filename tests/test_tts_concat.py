import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from mutagen.easyid3 import EasyID3

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


def _make_real_mp3(path):
    """Generate a tiny real MP3 (100ms of silence) using ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=8000:cl=mono", "-t", "0.1",
         "-c:a", "libmp3lame", "-b:a", "8k", "-y", str(path)],
        check=True,
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_tag_mp3_on_real_untagged_mp3(tmp_path):
    """Regression: tag_mp3 must handle MP3s with no existing ID3v2 tag."""
    mp3 = tmp_path / "real.mp3"
    _make_real_mp3(mp3)
    # No ID3 tag at this point
    tag_mp3(mp3, title="Hello Test")
    # Verify tag was written
    audio = EasyID3(str(mp3))
    assert audio["title"] == ["Hello Test"]
    assert "date" in audio


def test_pick_voice_returns_one_from_list():
    voices = ["alloy", "nova", "onyx"]
    assert pick_voice(voices) in voices


def test_pick_voice_empty_raises():
    import pytest
    with pytest.raises(ValueError, match="empty"):
        pick_voice([])
