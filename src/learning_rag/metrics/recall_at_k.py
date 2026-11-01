def recall_at_k(retrieved: list[str], expected: list[str], k: int = 5) -> float:
    if not expected:
        raise ValueError("no-answer questions are not scored by recall")
    if k <= 0:
        raise ValueError("k must be positive")
    found = set(retrieved[:k])
    relevant = set(expected)
    return len(found & relevant) / len(relevant)
