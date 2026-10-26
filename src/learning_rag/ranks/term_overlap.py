import math
import re

# shortcut: term overlap, not a neural embedding. Swap in sentence-transformers when that model is installed.

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokens(text: str) -> list[str]:
    # "Docstring," and "docstring" must be the same term, so case and punctuation are dropped.
    # Underscore stays, otherwise ``__doc__`` splits into empty pieces.
    return _TOKEN.findall(text.lower())


def term_freq(text: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in tokens(text):
        counts[token] = counts.get(token, 0.0) + 1.0
    return counts


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    # left and right are the two vectors. The angle is not an input.
    # cos(theta) = dot(left, right) / (|left| * |right|); theta itself is never computed.
    if not left or not right:
        return 0.0
    dot = sum(weight * right[token] for token, weight in left.items() if token in right)
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def top_k(
    query: str, chunks: list[tuple[int, str]], k: int = 5
) -> list[tuple[float, int, str]]:
    query_vec = term_freq(query)
    ranked = [
        (cosine(query_vec, term_freq(text)), start, text) for start, text in chunks
    ]
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:k]
