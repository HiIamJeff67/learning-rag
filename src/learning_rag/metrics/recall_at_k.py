def recall_at_k(retrieved: list[str], expected: list[str], k: int = 5) -> float:
    if not expected:
        raise ValueError("no-anwser questions are not scored by recall")
    found = set(retrieved[:k])
    return float(all(doc in found for doc in expected))
