from learning_rag.metrics.recall_at_k import recall_at_k

def test_recall_at_k_requires_every_expected_doc():
    assert recall_at_k(["a.rst", "b.rst"], ["a.rst"]) == 1
    assert recall_at_k(["a.rst"], ["a.rst", "b.rst"]) == 0
