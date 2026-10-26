import os

import pytest

from .settings import get_config, load_env_file, reset_config


@pytest.fixture(autouse=True)
def _fresh_config():
    reset_config()
    yield
    reset_config()


def test_openrouter_rejects_a_paid_model_id(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("MODEL_NAME", "openai/gpt-4o")
    with pytest.raises(ValueError):
        get_config(only_free_model=True)


def test_other_provider_keeps_its_model_name(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("MODEL_NAME", "qwen2.5:1.5b")
    _, base, model, *_ = get_config()
    assert base == "http://127.0.0.1:11434/v1"
    assert model == "qwen2.5:1.5b"


def test_free_flag_checks_a_cached_config(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("MODEL_NAME", "openai/gpt-4o")
    get_config()
    with pytest.raises(ValueError):
        get_config(only_free_model=True)


def test_config_is_read_once(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("MODEL_NAME", "first")
    first = get_config()
    monkeypatch.setenv("MODEL_NAME", "second")
    assert get_config() is first
    reset_config()
    assert get_config()[2] == "second"


def test_token_limits_come_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("MODEL_NAME", "qwen")
    monkeypatch.setenv("MODEL_MAX_TOKENS", "50")
    monkeypatch.setenv("MODEL_REASONING_TOKENS", "10")
    assert get_config()[3:] == (50, 10)


def test_load_env_file_does_not_override(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('MODEL_API_KEY="from-file"\nOTHER=1\n', encoding="utf-8")
    monkeypatch.setenv("MODEL_API_KEY", "already-set")
    monkeypatch.delenv("OTHER", raising=False)
    load_env_file(env_file)
    assert os.environ["MODEL_API_KEY"] == "already-set"
    assert os.environ["OTHER"] == "1"
