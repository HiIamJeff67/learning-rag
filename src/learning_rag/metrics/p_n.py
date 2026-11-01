from collections.abc import Iterable
from statistics import median

def p50(values: Iterable[float]) -> float | None:
    numbers = sorted(values)
    if not numbers:
        return None
    return round(median(numbers), 1)
