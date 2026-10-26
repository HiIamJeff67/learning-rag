def reciprocal_rank(retrieved: list[str], expected: list[str], k: int = 5) -> float:
    if not expected:
        raise ValueError("no-anwser questions are not scored by recall")
    for index, doc in enumerate(retrieved[:k], 1):
        if doc in expected:
            return 1 / index
    return 0.0
