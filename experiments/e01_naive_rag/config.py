from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: Path = CONFIG) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        config[key.strip()] = value.strip()
    return config


SETTINGS = load_config()
CORPUS = ROOT / SETTINGS["corpus"]
CHUNK_SIZE = int(SETTINGS["chunk_size"])
CHUNK_OVERLAP = int(SETTINGS["chunk_overlap"])
RANK_K = int(SETTINGS["rank_k"])
PROMPT_K = int(SETTINGS["prompt_k"])
