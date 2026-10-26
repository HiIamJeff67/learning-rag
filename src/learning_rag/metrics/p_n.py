from collections.abc import Iterable

def p50(values: Iterable[float]) -> float | None:
    numbers = sorted(values)
    if not numbers:
        return None
    return round(numbers[len(numbers) // 2], 1)
