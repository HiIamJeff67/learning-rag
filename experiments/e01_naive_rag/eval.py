import csv
import json
import time
from pathlib import Path
from typing import Any

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CORPUS, RANK_K, SETTINGS
from learning_rag.chunks.fixed import fixed_chunks_by_manifest, get_chunk_doc_id
from learning_rag.llm import complete
from learning_rag.metrics.recall_at_k import recall_at_k
from learning_rag.metrics.reciprocal_rank import  reciprocal_rank
from learning_rag.metrics.p_n import p50
from learning_rag.ranks.term_overlap import top_k

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "datasets" / "eval_questions.csv"
RESULTS = Path(__file__).resolve().parent / "results"
K = RANK_K


def evaluate() -> dict[str, Any]:
    chunks = fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []

    with QUESTIONS.open(encoding="utf-8", newline="") as handle:
        questions = list(csv.DictReader(handle))
        for index, item in enumerate(questions, 1):
            print(f"{index}/{len(questions)} {item['type']}", flush=True)
            expected = [doc for doc in item["expected_doc_ids"].split("|") if doc]
            started = time.perf_counter()
            hits = top_k(item["question"], chunks, k=K)
            retrieval_ms = (time.perf_counter() - started) * 1000
            context = "\n\n".join(f"[start={start}] {text.strip()}" for _, start, text in hits)
            prompt = (
                "Answer from the context only. If the context does not say, reply: I do not know.\n\n"
                f"Context:\n{context}\n\nQuestion: {item['question']}"
            )
            answer_started = time.perf_counter()
            try:
                answer = complete(prompt, only_free_model=True)
                answer_error = None
            except Exception as exc:
                answer = None
                answer_error = str(exc)
            e2e_ms = retrieval_ms + (time.perf_counter() - answer_started) * 1000
            retrieved = [get_chunk_doc_id(text) for _, _, text in hits]
            row: dict[str, Any] = {
                "question": item["question"],
                "type": item["type"],
                "expected": expected,
                "retrieved": retrieved,
                "retrieval_ms": round(retrieval_ms, 1),
                "e2e_ms": round(e2e_ms, 1),
                "answer": answer,
                "answer_error": answer_error,
            }
            if expected:
                row["recall_at_5"] = recall_at_k(retrieved, expected, K)
                row["mrr"] = reciprocal_rank(retrieved, expected, K)
                scored.append(row)
                if row["recall_at_5"] == 0:
                    failures.append(row)
            else:
                row["no_answer"] = True
            rows.append(row)

    metrics = {
        "questions": len(rows),
        "scored_questions": len(scored),
        "recall_at_5": round(sum(row["recall_at_5"] for row in scored) / len(scored), 3),
        "mrr": round(sum(row["mrr"] for row in scored) / len(scored), 3),
        "retrieval_ms_p50": p50(row["retrieval_ms"] for row in rows),
        "e2e_ms_p50": p50(row["e2e_ms"] for row in rows if row["answer_error"] is None),
        "e2e_errors": sum(row["answer_error"] is not None for row in rows),
        "config": SETTINGS,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "failures.json").write_text(
        json.dumps(failures[:10], indent=2) + "\n", encoding="utf-8"
    )
    return metrics


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
