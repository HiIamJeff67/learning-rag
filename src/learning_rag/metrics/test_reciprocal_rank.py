from learning_rag.metrics.reciprocal_rank import reciprocal_rank

def test_reciprocal_rank_uses_the_first_hit():
    assert reciprocal_rank(["other.rst", "a.rst"], ["a.rst"]) == 0.5
    assert reciprocal_rank(["other.rst"], ["a.rst"]) == 0
