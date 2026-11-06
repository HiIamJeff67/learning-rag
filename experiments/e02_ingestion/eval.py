from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
import time
from typing import Any

from learning_rag.metrics.p_n import p50
from learning_rag.metrics.recall_at_k import recall_at_k
from learning_rag.metrics.reciprocal_rank import reciprocal_rank

from .chunk import STRATEGIES, ChunkSpec
from .index import search_index, sources_in, sync_index


def compare(corpus: Path, questions: Path, output: Path) -> dict[str, Any]:
    with questions.open(encoding="utf-8-sig", newline="") as handle:
        cases = list(csv.DictReader(handle))
    if not cases:
        raise ValueError("question set is empty")
    sources = sources_in(corpus)
    source_ids = {source.source_id for source in sources}
    expected = [row["expected_doc_ids"].split("|") if row["expected_doc_ids"] else [] for row in cases]
    unknown = sorted({source for labels in expected for source in labels} - source_ids)
    if unknown:
        raise ValueError(f"questions refer to missing sources: {', '.join(unknown)}")
    corpus_hash = hashlib.sha256()
    for source in sources:
        corpus_hash.update(source.path.encode() + b"\0")
        corpus_hash.update(source.file.read_bytes())
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    k = 5
    summary: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": corpus_hash.hexdigest(),
        "questions_sha256": hashlib.sha256(questions.read_bytes()).hexdigest(),
        "questions": len(cases),
        "scored_questions": sum(bool(labels) for labels in expected),
        "vector": "term-frequency",
        "similarity": "cosine",
        "rank_k": k,
        "runs": {},
    }
    all_rows: dict[str, list[dict[str, Any]]] = {}
    with TemporaryDirectory(prefix="indexes-", dir=output) as temporary:
        for strategy in STRATEGIES:
            for overlap in (0, 80):
                name = f"{strategy}-500-{overlap}"
                print(f"Building {name}", flush=True)
                index = Path(temporary) / f"{name}.sqlite3"
                spec = ChunkSpec(strategy, 500, overlap)
                costs = sync_index(index, corpus, spec)
                rows: list[dict[str, Any]] = []
                grouped: dict[str, list[tuple[float, float]]] = defaultdict(list)
                for row, labels in zip(cases, expected):
                    started = time.perf_counter()
                    hits = search_index(index, row["question"], k)
                    elapsed = (time.perf_counter() - started) * 1000
                    retrieved = [hit["source_id"] for hit in hits]
                    recall = recall_at_k(retrieved, labels, k) if labels else None
                    rr = reciprocal_rank(retrieved, labels, k) if labels else None
                    if recall is not None and rr is not None:
                        grouped[row["type"]].append((recall, rr))
                    rows.append({
                        "question": row["question"],
                        "type": row["type"],
                        "expected": labels,
                        "recall_at_5": recall,
                        "rr_at_5": rr,
                        "retrieval_ms": round(elapsed, 3),
                        "hits": [
                            {key: hit[key] for key in ("source_id", "offset", "section", "page", "score")}
                            for hit in hits
                        ],
                    })
                scores = [score for group in grouped.values() for score in group]
                summary["runs"][name] = {
                    **costs,
                    "strategy": strategy,
                    "size": spec.size,
                    "overlap": overlap,
                    "recall_at_5": round(mean(score[0] for score in scores), 6) if scores else None,
                    "mrr_at_5": round(mean(score[1] for score in scores), 6) if scores else None,
                    "retrieval_ms_p50": p50(row["retrieval_ms"] for row in rows),
                    "by_type": {
                        name: {
                            "questions": len(pairs),
                            "recall_at_5": round(mean(score[0] for score in pairs), 6),
                            "mrr_at_5": round(mean(score[1] for score in pairs), 6),
                        }
                        for name, pairs in sorted(grouped.items())
                    },
                }
                all_rows[name] = rows
    for name, payload in [("metrics", summary), ("questions", all_rows)]:
        (output / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return summary
