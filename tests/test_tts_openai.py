from pathlib import Path
from unittest.mock import MagicMock, patch
from karakeep_tts.tts import synthesize_article


def test_synthesize_article_calls_openai_per_chunk(tmp_path):
    fake_client = MagicMock()
    # streaming response yields bytes
    fake_response = MagicMock()
    fake_response.iter_bytes.return_value = [b"audio-data"]
    fake_client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value = fake_response

    chunks = ["chunk one", "chunk two", "chunk three"]
    output_dir = tmp_path / "chunks"
    output_dir.mkdir()

    paths = synthesize_article(
        client=fake_client,
        chunks=chunks,
        voice="alloy",
        model="gpt-4o-mini-tts",
        instructions="narrator voice",
        output_dir=output_dir,
    )

    assert len(paths) == 3
    for i, p in enumerate(paths):
        assert p.name == f"chunk_{i:03d}.mp3"
        assert p.read_bytes() == b"audio-data"

    # All chunks use the same voice and model
    calls = fake_client.audio.speech.with_streaming_response.create.call_args_list
    assert len(calls) == 3
    for call in calls:
        assert call.kwargs["voice"] == "alloy"
        assert call.kwargs["model"] == "gpt-4o-mini-tts"
        assert call.kwargs["instructions"] == "narrator voice"


def test_synthesize_article_skips_instructions_for_tts_1(tmp_path):
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.iter_bytes.return_value = [b"x"]
    fake_client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value = fake_response

    synthesize_article(
        client=fake_client,
        chunks=["c"],
        voice="alloy",
        model="tts-1",
        instructions="ignored",
        output_dir=tmp_path,
    )
    call = fake_client.audio.speech.with_streaming_response.create.call_args
    assert "instructions" not in call.kwargs
