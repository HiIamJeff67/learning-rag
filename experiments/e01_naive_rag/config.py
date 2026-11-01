import hashlib
import platform
from pathlib import Path
from typing import Any

from learning_rag.shared.settings import get_config

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
SEED = int(SETTINGS["seed"])
TEMPERATURE = float(SETTINGS["temperature"])
REASONING_EFFORT = SETTINGS["reasoning_effort"]

if SETTINGS["chunker"] != "fixed-characters" or SETTINGS["ranker"] != "term-overlap-cosine":
    raise ValueError("this experiment only implements fixed-characters and term-overlap-cosine")
if not 0 < PROMPT_K <= RANK_K:
    raise ValueError("require 0 < prompt_k <= rank_k")


def run_config(with_answer: bool, only_free_model: bool = False) -> dict[str, Any]:
    names = (CORPUS / "MANIFEST.txt").read_text(encoding="utf-8").split()
    corpus_hash = hashlib.sha256()
    for name in names:
        corpus_hash.update(name.encode() + b"\0")
        corpus_hash.update((CORPUS / name).read_bytes())
    files = [
        "experiments/e01_naive_rag/config.yaml",
        "experiments/e01_naive_rag/config.py",
        "experiments/e01_naive_rag/run.py",
        "experiments/e01_naive_rag/eval.py",
        "src/learning_rag/chunks/fixed.py",
        "src/learning_rag/ranks/term_overlap.py",
        "src/learning_rag/metrics/recall_at_k.py",
        "src/learning_rag/metrics/reciprocal_rank.py",
        "src/learning_rag/metrics/p_n.py",
        "src/learning_rag/llm.py",
        "src/learning_rag/shared/settings.py",
    ]
    config: dict[str, Any] = {
        **SETTINGS,
        "python": platform.python_version(),
        "documents": len(names),
        "corpus_sha256": corpus_hash.hexdigest(),
        "corpus_source": (ROOT / "data/raw/SOURCE.txt").read_text(encoding="utf-8"),
        "questions_sha256": hashlib.sha256((ROOT / "datasets/eval_questions.csv").read_bytes()).hexdigest(),
        "implementation_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files
        },
        "generation": None,
    }
    if with_answer:
        _, base, model, max_tokens, reasoning_tokens = get_config(only_free_model)
        config["generation"] = {
            "base_url": base,
            "model": model,
            "max_tokens": max_tokens,
            "reasoning_tokens": reasoning_tokens,
            "reasoning_effort": REASONING_EFFORT,
        }
    return config
