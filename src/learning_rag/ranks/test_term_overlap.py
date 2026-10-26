from learning_rag.chunks.fixed import fixed_chunks

from .term_overlap import top_k

TEXT = (
    "alpha beta gamma. " * 20
    + "A docstring is a string literal in a function. "
    + "delta epsilon zeta. " * 20
)


def test_matching_phrase_ranks_first():
    chunks = fixed_chunks(TEXT, size=80, overlap=0)
    hits = top_k("what is a docstring", chunks, k=1)
    assert "docstring is a string literal" in hits[0][2]
