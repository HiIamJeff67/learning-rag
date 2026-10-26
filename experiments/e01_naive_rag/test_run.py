import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "raw" / "peps"


def test_corpus_has_100_pinned_documents():
    names = (CORPUS / "MANIFEST.txt").read_text(encoding="utf-8").split()
    assert len(names) >= 100
    assert all((CORPUS / name).is_file() for name in names)


def test_rank_prints_the_definition_passage():
    result = subprocess.run(
        [sys.executable, "-m", "experiments.e01_naive_rag.run", "string literal that occurs as the first statement"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert "first statement" in result.stdout
