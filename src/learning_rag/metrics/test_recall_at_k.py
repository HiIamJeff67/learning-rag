from learning_rag.metrics.recall_at_k import recall_at_k
import pytest


def test_recall_counts_partial_coverage():
    assert recall_at_k(["a.rst", "b.rst"], ["a.rst"]) == 1
    assert recall_at_k(["a.rst"], ["a.rst", "b.rst"]) == 0.5


def test_duplicate_chunks_do_not_increase_recall_or_expand_k():
    assert recall_at_k(["a", "a", "b"], ["a", "b"], 2) == 0.5
    assert recall_at_k(["a"], ["a", "a", "b"]) == 0.5


def test_no_answer_and_invalid_k_are_not_scored():
    with pytest.raises(ValueError):
        recall_at_k(["a"], [])
    with pytest.raises(ValueError):
        recall_at_k(["a"], ["a"], 0)
