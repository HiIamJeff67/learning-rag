from pathlib import Path

# shortcut: cuts by character, not token or heading. Upgrade when a chunk must stay inside one section.


def fixed_chunks(text: str, size: int = 500, overlap: int = 80) -> list[tuple[int, str]]:
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")
    step = size - overlap
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        piece = text[start : start + size]
        if piece.strip():
            chunks.append((start, piece))
        if start + size >= len(text):
            break
        start += step
    return chunks


def fixed_chunks_by_manifest(
    directory: Path, size: int = 500, overlap: int = 80
) -> list[tuple[int, str]]:
    names = (directory / "MANIFEST.txt").read_text(encoding="utf-8").split()
    chunks: list[tuple[int, str]] = []
    for name in names:
        text = (directory / name).read_text(encoding="utf-8")
        for start, piece in fixed_chunks(text, size, overlap):
            chunks.append((start, f"[{name}]\n{piece}"))
    return chunks


def get_chunk_doc_id(chunk: str) -> str:
   return chunk.split("]", 1)[0][1:]
