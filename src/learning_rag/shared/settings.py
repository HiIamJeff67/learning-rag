import os
from pathlib import Path

# shortcut: KEY=VALUE only, no export/comments. Upgrade if a value needs a comment or multiline.
# One process keeps one config. Call reset_config() in tests before changing MODEL_*.

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "recursive/flint-v1.0:free"

_config: tuple[str, str, str, int, int] | None = None


def load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() and name.strip() not in os.environ:
            os.environ[name.strip()] = value.strip().strip('"').strip("'")


def reset_config() -> None:
    global _config
    _config = None


def _int_setting(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    return int(raw) if raw else default


def get_config(only_free_model: bool = False) -> tuple[str, str, str, int, int]:
    global _config
    if _config is None:
        load_env_file()
        key = os.environ.get("MODEL_API_KEY", "")
        base = os.environ.get("MODEL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        model = os.environ.get("MODEL_NAME", DEFAULT_MODEL)
        if not key:
            raise RuntimeError("MODEL_API_KEY is missing")
        if not base or not model:
            raise RuntimeError("MODEL_BASE_URL and MODEL_NAME are missing")
        _config = (
            key,
            base,
            model,
            _int_setting("MODEL_MAX_TOKENS", 1200),
            _int_setting("MODEL_REASONING_TOKENS", 400),
        )
    _, base, model, _, _ = _config
    # Checked on every call. A cached config must not skip a later --free run.
    if only_free_model and "openrouter.ai" in base and not model.endswith(":free"):
        raise ValueError("OpenRouter calls must use a :free model id")
    return _config
