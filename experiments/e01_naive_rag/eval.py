import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CORPUS, RANK_K, run_config
from .run import run_query
from learning_rag.chunks.fixed import fixed_chunks_by_manifest
from learning_rag.metrics.recall_at_k import recall_at_k
from learning_rag.metrics.reciprocal_rank import reciprocal_rank
from learning_rag.metrics.p_n import p50

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "datasets" / "eval_questions.csv"
RESULTS = Path(__file__).resolve().parent / "results"


def evaluate(
    *, with_answer: bool = False, only_free_model: bool = False,
    output: Path = RESULTS,
) -> dict[str, Any]:
    config = run_config(with_answer, only_free_model)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    chunks = fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP)
    ingestion_ms = round((time.perf_counter() - started) * 1000, 3)
    rows: list[dict[str, Any]] = []
    with QUESTIONS.open(encoding="utf-8", newline="") as handle:
        questions = list(csv.DictReader(handle))
    if not questions:
        raise ValueError("question set is empty")
    for index, item in enumerate(questions, 1):
        expected = [doc for doc in item["expected_doc_ids"].split("|") if doc]
        print(f"{index}/{len(questions)} {item['type']}", flush=True)
        row = run_query(item["question"], chunks, with_answer=with_answer, only_free_model=only_free_model)
        row.update(type=item["type"], expected=expected)
        row["recall_at_5"] = recall_at_k(row["retrieved"], expected, RANK_K) if expected else None
        row["mrr_at_5"] = reciprocal_rank(row["retrieved"], expected, RANK_K) if expected else None
        row["all_docs_at_5"] = set(expected) <= set(row["retrieved"]) if expected else None
        row["context_recall"] = len(set(expected) & set(row["context_doc_ids"])) / len(set(expected)) if expected else None
        row["refused"] = row["answer"].strip() == "I do not know." if row["answer"] is not None else None
        rows.append(row)

    scored = [row for row in rows if row["expected"]]
    failures = [row for row in scored if row["recall_at_5"] < 1]
    summary: dict[str, Any] = {}
    for name in ["all", *sorted({row["type"] for row in rows})]:
        group = rows if name == "all" else [row for row in rows if row["type"] == name]
        relevant = [row for row in group if row["expected"]]
        summary[name] = {
            "questions": len(group),
            "scored_questions": len(relevant),
        }
        for metric in ["recall_at_5", "mrr_at_5", "all_docs_at_5", "context_recall"]:
            summary[name][metric] = (
                round(sum(row[metric] for row in relevant) / len(relevant), 6)
                if relevant else None
            )
    no_answer = [row for row in rows if not row["expected"]]
    metrics: dict[str, Any] = {
        "started_at": started_at,
        "mode": "generation" if with_answer else "retrieval",
        **summary.pop("all"),
        "by_type": summary,
        "ingestion_ms": ingestion_ms,
        "retrieval_ms_p50": p50(row["retrieval_ms"] for row in rows),
        "e2e_ms_p50": p50(row["e2e_ms"] for row in rows if row["e2e_ms"] is not None),
        "successful_e2e_ms_p50": p50(row["e2e_ms"] for row in rows if row["answer"] is not None),
        "generation_attempts": len(rows) if with_answer else 0,
        "generation_errors": sum(row["answer_error"] is not None for row in rows),
        "no_answer_refusals": sum(row["refused"] is True for row in no_answer) if with_answer else None,
        "no_answer_questions": len(no_answer),
        "retrieval_failures": len(failures),
        "config": config,
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in [("metrics", metrics), ("questions", rows), ("failures", failures[:10])]:
        (output / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer", action="store_true")
    parser.add_argument("--free", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or (RESULTS if args.answer else RESULTS / "retrieval")
    metrics = evaluate(with_answer=args.answer, only_free_model=args.free, output=output)
    print(json.dumps(metrics, indent=2))
    if metrics["generation_errors"]:
        raise SystemExit(1)
