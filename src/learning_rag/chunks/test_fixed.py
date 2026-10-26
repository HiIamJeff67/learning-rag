from pathlib import Path

import pytest

from .fixed import fixed_chunks_by_manifest, fixed_chunks


def test_overlap_moves_the_window():
    chunks = fixed_chunks("abcdefghij", size=4, overlap=1)
    assert [start for start, _ in chunks] == [0, 3, 6]
    assert chunks[-1][1] == "ghij"


def test_empty():
    assert fixed_chunks("") == []


def test_bad_overlap():
    with pytest.raises(ValueError):
        fixed_chunks("abc", size=2, overlap=2)


def test_manifest_tags_each_chunk_with_its_file(tmp_path: Path):
    (tmp_path / "a.rst").write_text("hello", encoding="utf-8")
    (tmp_path / "MANIFEST.txt").write_text("a.rst\n", encoding="utf-8")
    chunks = fixed_chunks_by_manifest(tmp_path, size=20, overlap=0)
    assert chunks == [(0, "[a.rst]\nhello")]
