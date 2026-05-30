import pytest
from karakeep_tts.config import Config


def test_config_loads_required_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("KARAKEEP_API_KEY", "kk-test")
    monkeypatch.setenv("KARAKEEP_API_HOST", "karakeep.example.com")
    monkeypatch.setenv("OVERCAST_EMAIL", "user@example.com")
    monkeypatch.setenv("OVERCAST_PASSWORD", "secret")
    cfg = Config.from_env()
    assert cfg.openai_api_key == "sk-test"
    assert cfg.karakeep_api_key == "kk-test"
    assert cfg.karakeep_api_host == "karakeep.example.com"
    assert cfg.overcast_email == "user@example.com"
    assert cfg.overcast_password == "secret"


def test_config_defaults(monkeypatch):
    for k in ["OPENAI_API_KEY", "KARAKEEP_API_KEY", "KARAKEEP_API_HOST",
              "OVERCAST_EMAIL", "OVERCAST_PASSWORD"]:
        monkeypatch.setenv(k, "x")
    cfg = Config.from_env()
    assert cfg.bookmark_list_name == "Instapaper"
    assert cfg.media_path.name == "media"
    assert cfg.openai_tts_model == "gpt-4o-mini-tts"
    assert cfg.max_chunk_chars == 3800
    assert cfg.sleep_interval == 60
    assert "alloy" in cfg.openai_tts_voices
    assert len(cfg.openai_tts_voices) == 10


def test_config_voices_comma_split(monkeypatch):
    for k in ["OPENAI_API_KEY", "KARAKEEP_API_KEY", "KARAKEEP_API_HOST",
              "OVERCAST_EMAIL", "OVERCAST_PASSWORD"]:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("OPENAI_TTS_VOICES", "alloy, nova, onyx")
    cfg = Config.from_env()
    assert cfg.openai_tts_voices == ["alloy", "nova", "onyx"]


def test_config_missing_required_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("KARAKEEP_API_KEY", "x")
    monkeypatch.setenv("KARAKEEP_API_HOST", "x")
    monkeypatch.setenv("OVERCAST_EMAIL", "x")
    monkeypatch.setenv("OVERCAST_PASSWORD", "x")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Config.from_env()
