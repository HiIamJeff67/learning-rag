from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any

from learning_rag.ranks.term_overlap import term_freq

from .chunk import ChunkSpec, chunk_document
from .parse import SUFFIXES, parse_document


_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    config TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    position INTEGER NOT NULL,
    raw_sha256 TEXT NOT NULL,
    parsed_sha256 TEXT NOT NULL,
    version TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    permissions TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    section TEXT NOT NULL,
    page INTEGER,
    norm REAL NOT NULL,
    UNIQUE(source_id, ordinal)
);
CREATE TABLE IF NOT EXISTS postings (
    term TEXT NOT NULL,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    weight REAL NOT NULL,
    PRIMARY KEY(term, chunk_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS postings_by_chunk ON postings(chunk_id);
"""


@dataclass(frozen=True)
class Source:
    file: Path
    path: str
    source_id: str
    version: str | None
    updated_at: str
    permissions: tuple[str, ...]


def sources_in(corpus: Path) -> list[Source]:
    root = corpus.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"corpus must be a directory: {root}")
    manifest = root / "MANIFEST.txt"
    if manifest.is_file():
        lines = manifest.read_text(encoding="utf-8-sig").splitlines()
        names = [line.strip() for line in lines if line.strip()]
    else:
        names = sorted(
            file.relative_to(root).as_posix()
            for file in root.rglob("*")
            if file.is_file() and file.suffix.lower() in SUFFIXES
        )
    sidecar = root / "metadata.json"
    metadata = json.loads(sidecar.read_text(encoding="utf-8-sig")) if sidecar.exists() else {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json must map relative paths to metadata objects")
    sources: list[Source] = []
    ids: set[str] = set()
    paths: set[Path] = set()
    for name in names:
        file = (root / name).resolve(strict=True)
        if not file.is_relative_to(root) or not file.is_file() or file.suffix.lower() not in SUFFIXES:
            raise ValueError(f"invalid document path in corpus: {name}")
        path = file.relative_to(root).as_posix()
        info = metadata.get(path, {})
        if not isinstance(info, dict):
            raise ValueError(f"metadata for {path} must be an object")
        source_id = info.get("source_id", path)
        version = info.get("version")
        updated_at = info.get("updated_at")
        permissions = info.get("permissions", [])
        if not isinstance(source_id, str) or not source_id.strip() or source_id in ids or file in paths:
            raise ValueError(f"missing or duplicate source ID/path: {path}")
        if version is not None and (not isinstance(version, str) or not version.strip()):
            raise ValueError(f"version must be a nonempty string: {path}")
        if updated_at is not None and (not isinstance(updated_at, str) or not updated_at.strip()):
            raise ValueError(f"updated_at must be a nonempty string: {path}")
        if not isinstance(permissions, list) or not all(isinstance(value, str) for value in permissions):
            raise ValueError(f"permissions must be a list of strings: {path}")
        ids.add(source_id)
        paths.add(file)
        sources.append(Source(
            file, path, source_id, version,
            updated_at or datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat(),
            tuple(sorted(set(permissions))),
        ))
    return sources


def sync_index(
    index: Path, corpus: Path, spec: ChunkSpec, *, prune: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    sources = sources_in(corpus)
    index.parent.mkdir(parents=True, exist_ok=True)
    config = json.dumps({"version": 1, "vector": "term-frequency", **asdict(spec)}, sort_keys=True)
    stats: dict[str, Any] = dict(added=0, rebuilt=0, metadata_only=0, reused=0, deleted=0)
    embedding_ms = 0.0
    vectors_written = 0
    with closing(sqlite3.connect(index, timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            settings = conn.execute("SELECT config FROM settings").fetchone()
            if settings is None:
                conn.execute("INSERT INTO settings VALUES (1, ?)", (config,))
            elif settings["config"] != config:
                raise ValueError("index configuration differs; choose a new --index path")
            previous = {
                row["source_id"]: row for row in conn.execute("SELECT * FROM sources")
            }
            for position, source in enumerate(sources):
                before = previous.get(source.source_id)
                data = source.file.read_bytes()
                raw_hash = hashlib.sha256(data).hexdigest()
                parsed = None
                suffix = source.file.suffix.lower()
                if (
                    before is not None
                    and before["raw_sha256"] == raw_hash
                    and Path(before["path"]).suffix.lower() == suffix
                ):
                    parsed_hash = before["parsed_sha256"]
                else:
                    parsed = parse_document(data, suffix)
                    if suffix == ".pdf" and not parsed.text.strip():
                        raise ValueError(f"PDF has no extractable text: {source.path}")
                    parsed_hash = hashlib.sha256(
                        json.dumps(asdict(parsed), sort_keys=True).encode("utf-8")
                    ).hexdigest()

                values = (
                    source.path, position, raw_hash, parsed_hash, source.version or raw_hash,
                    source.updated_at, json.dumps(source.permissions),
                )
                if before is not None and tuple(before)[1:] == values:
                    stats["reused"] += 1
                    continue
                conn.execute(
                    """INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        path=excluded.path, position=excluded.position,
                        raw_sha256=excluded.raw_sha256, parsed_sha256=excluded.parsed_sha256,
                        version=excluded.version, updated_at=excluded.updated_at,
                        permissions=excluded.permissions""",
                    (source.source_id, *values),
                )
                if before is not None and before["parsed_sha256"] == parsed_hash:
                    stats["metadata_only"] += 1
                    continue
                assert parsed is not None
                stats["added" if before is None else "rebuilt"] += 1
                conn.execute("DELETE FROM chunks WHERE source_id = ?", (source.source_id,))
                for ordinal, chunk in enumerate(chunk_document(parsed, spec)):
                    embed_started = time.perf_counter()
                    vector = term_freq(f"[{source.source_id}]\n{chunk.text}")
                    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
                    embedding_ms += (time.perf_counter() - embed_started) * 1000
                    cursor = conn.execute(
                        """INSERT INTO chunks(source_id, ordinal, offset, text, section, page, norm)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (source.source_id, ordinal, chunk.start, chunk.text, chunk.section, chunk.page, norm),
                    )
                    conn.executemany(
                        "INSERT INTO postings VALUES (?, ?, ?)",
                        ((term, cursor.lastrowid, weight) for term, weight in vector.items()),
                    )
                    vectors_written += 1
            if prune:
                removed = previous.keys() - {source.source_id for source in sources}
                conn.executemany("DELETE FROM sources WHERE source_id = ?", ((sid,) for sid in removed))
                stats["deleted"] = len(removed)
            stats["documents"] = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            stats["chunks"] = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            stats["postings"] = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    return {
        **stats, "vectors_written": vectors_written,
        "embedding_ms": round(embedding_ms, 3),
        "ingestion_ms": round((time.perf_counter() - started) * 1000, 3),
        "index_bytes": index.stat().st_size,
    }


def delete_source(index: Path, source_id: str) -> bool:
    with closing(sqlite3.connect(index.resolve(strict=True), timeout=30)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            return bool(conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,)).rowcount)


def search_index(index: Path, query: str, k: int = 5) -> list[dict[str, Any]]:
    if k <= 0:
        raise ValueError("k must be positive")
    vector = term_freq(query)
    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
    with closing(sqlite3.connect(index.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """WITH matches AS (
                SELECT p.chunk_id, SUM(p.weight * q.value) AS dot
                FROM json_each(?) q JOIN postings p ON p.term = q.key
                GROUP BY p.chunk_id
            )
            SELECT c.id AS chunk_id, c.source_id, c.offset, c.text, c.section, c.page,
                s.path, s.version, s.updated_at, s.permissions,
                COALESCE(matches.dot / NULLIF(c.norm * ?, 0), 0.0) AS score
            FROM chunks c JOIN sources s ON s.source_id = c.source_id
            LEFT JOIN matches ON matches.chunk_id = c.id
            ORDER BY score DESC, s.position, c.source_id, c.ordinal
            LIMIT ?""",
            (json.dumps(vector), norm, k),
        ).fetchall()
    return [dict(row) | {"permissions": json.loads(row["permissions"])} for row in rows]
