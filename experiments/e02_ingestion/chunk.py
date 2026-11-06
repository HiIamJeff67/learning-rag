from bisect import bisect_right
from dataclasses import dataclass
from itertools import groupby

from learning_rag.chunks.fixed import fixed_chunks

from .parse import Document


STRATEGIES = ("fixed", "recursive", "section")


@dataclass(frozen=True)
class ChunkSpec:
    strategy: str = "section"
    size: int = 500
    overlap: int = 0

    def __post_init__(self) -> None:
        if self.strategy not in STRATEGIES:
            raise ValueError(f"unknown chunk strategy: {self.strategy}")
        if self.size <= 0 or not 0 <= self.overlap < self.size:
            raise ValueError("require size > 0 and 0 <= overlap < size")


@dataclass(frozen=True)
class Chunk:
    start: int
    text: str
    section: str
    page: int | None


def _split_units(
    text: str, start: int, end: int, size: int, separators: tuple[str, ...],
) -> list[tuple[int, int]]:
    if end - start <= size:
        return [(start, end)]
    if not separators:
        return [(offset, min(offset + size, end)) for offset in range(start, end, size)]
    separator = separators[0]
    units: list[tuple[int, int]] = []
    while start < end:
        found = text.find(separator, start, end)
        stop = found + len(separator) if found >= 0 else end
        units.extend(_split_units(text, start, stop, size, separators[1:]))
        start = stop
    return units


def _pack_units(units: list[tuple[int, int]], spec: ChunkSpec) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    first = 0
    while first < len(units):
        start = units[first][0]
        last = first + 1
        while last < len(units) and units[last][1] - start <= spec.size:
            last += 1
        end = units[last - 1][1]
        chunks.append((start, end))
        if last == len(units):
            break
        next_first = last
        # Repeat complete units, while leaving space for at least one new unit.
        while next_first > first + 1:
            repeat = units[next_first - 1][0]
            if end - repeat > spec.overlap or units[last][1] - repeat > spec.size:
                break
            next_first -= 1
        first = next_first
    return chunks


def chunk_document(document: Document, spec: ChunkSpec) -> list[Chunk]:
    chunks: list[Chunk] = []
    offsets = [span.start for span in document.spans]
    groups = groupby(
        document.spans,
        key=lambda span: (span.page, span.section if spec.strategy == "section" else ""),
    )
    for (page, section), group in groups:
        spans = list(group)
        start, end = spans[0].start, spans[-1].end
        if spec.strategy == "fixed":
            ranges = [
                (start + offset, start + offset + len(piece))
                for offset, piece in fixed_chunks(document.text[start:end], spec.size, spec.overlap)
            ]
        else:
            if spec.strategy == "section":
                units = [
                    unit
                    for span in spans
                    for unit in _split_units(
                        document.text, span.start, span.end, spec.size,
                        ("\n",) if span.kind == "code" else ("\n", " "),
                    )
                ]
            else:
                units = _split_units(document.text, start, end, spec.size, ("\n\n", "\n", " "))
            ranges = _pack_units(units, spec)
        for left, right in ranges:
            body = document.text[left:right]
            if not body.strip():
                continue
            label = document.spans[bisect_right(offsets, left) - 1].section
            if spec.strategy == "section" and section and not body.lstrip().startswith(section):
                body = f"{section}\n\n{body}"
            chunks.append(Chunk(left, body, label, page))
    return chunks
