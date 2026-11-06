from contextlib import closing
import json
import sqlite3

import pytest

from learning_rag.chunks.fixed import fixed_chunks_by_manifest
from learning_rag.ranks.term_overlap import top_k

from .chunk import ChunkSpec
from .index import delete_source, search_index, sync_index


def test_index_matches_baseline_scores_and_manifest_tie_order(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "b.rst").write_text("a refund goes back to the card", encoding="utf-8")
    (corpus / "a.rst").write_text("a refund goes back to the card", encoding="utf-8")
    (corpus / "MANIFEST.txt").write_text("b.rst\na.rst\n", encoding="utf-8")
    index = tmp_path / "index.sqlite3"
    sync_index(index, corpus, ChunkSpec("fixed", 500, 80))
    for question in ["refund", "unknown"]:
        baseline = top_k(question, fixed_chunks_by_manifest(corpus))
        actual = search_index(index, question)
        assert [(hit["score"], hit["offset"], f"[{hit['source_id']}]\n{hit['text']}")
                for hit in actual] == baseline


def test_reimport_and_format_or_permission_changes_reuse_vectors(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    path = corpus / "return.md"
    path.write_bytes(b"# Policy\r\n\r\nReturns within 14 days.\r\n")
    index = tmp_path / "index.sqlite3"
    spec = ChunkSpec()
    first = sync_index(index, corpus, spec)
    [hit] = search_index(index, "returns")
    again = sync_index(index, corpus, spec)
    assert first["chunks"] == again["chunks"] == 1
    assert again["reused"] == 1 and again["vectors_written"] == 0

    path.write_bytes(b"# Policy\n\nReturns within 14 days.\n")
    (corpus / "metadata.json").write_text(
        json.dumps({"return.md": {"version": "v4", "permissions": ["support"]}}),
        encoding="utf-8",
    )
    changed = sync_index(index, corpus, spec)
    [updated] = search_index(index, "returns")
    assert changed["metadata_only"] == 1 and changed["vectors_written"] == 0
    assert updated["chunk_id"] == hit["chunk_id"]
    assert updated["version"] == "v4" and updated["permissions"] == ["support"]


def test_replace_and_remove_delete_old_postings(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    returns = corpus / "return.txt"
    returns.write_text("returns fourteen", encoding="utf-8")
    shipping = corpus / "shipping.txt"
    shipping.write_text("shipping price", encoding="utf-8")
    index = tmp_path / "index.sqlite3"
    spec = ChunkSpec()
    sync_index(index, corpus, spec)
    before = next(hit for hit in search_index(index, "shipping") if hit["source_id"] == "shipping.txt")
    returns.write_text("returns seven", encoding="utf-8")
    updated = sync_index(index, corpus, spec)
    hits = search_index(index, "fourteen")
    assert updated["rebuilt"] == 1 and updated["reused"] == 1
    assert all(hit["score"] == 0 and "fourteen" not in hit["text"] for hit in hits)
    assert next(hit for hit in hits if hit["source_id"] == "shipping.txt")["chunk_id"] == before["chunk_id"]

    shipping.unlink()
    assert sync_index(index, corpus, spec, prune=True)["deleted"] == 1
    assert delete_source(index, "return.txt")
    assert not delete_source(index, "return.txt")
    assert search_index(index, "returns") == []
    with closing(sqlite3.connect(index)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_failed_import_rolls_back_earlier_updates(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    first = corpus / "a.txt"
    last = corpus / "z.txt"
    first.write_text("old return rule", encoding="utf-8")
    last.write_text("shipping policy", encoding="utf-8")
    index = tmp_path / "index.sqlite3"
    spec = ChunkSpec()
    sync_index(index, corpus, spec)
    old = search_index(index, "return")
    first.write_text("new return rule", encoding="utf-8")
    last.write_bytes(b"\xff\xfe")
    with pytest.raises(UnicodeDecodeError):
        sync_index(index, corpus, spec)
    assert search_index(index, "return") == old


def test_strategy_changes_require_a_separate_index(tmp_path):
    corpus = tmp_path / "docs"
    corpus.mkdir()
    (corpus / "a.txt").write_text("refund", encoding="utf-8")
    index = tmp_path / "index.sqlite3"
    sync_index(index, corpus, ChunkSpec())
    with pytest.raises(ValueError, match="configuration differs"):
        sync_index(index, corpus, ChunkSpec("fixed"))
    assert search_index(index, "refund")[0]["score"] > 0
