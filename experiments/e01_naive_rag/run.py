import argparse
import json
import time
from pathlib import Path
from typing import Any

from .config import (
    CHUNK_OVERLAP, CHUNK_SIZE, CORPUS, PROMPT_K, RANK_K,
    REASONING_EFFORT, SEED, TEMPERATURE, run_config,
)
from learning_rag.chunks.fixed import fixed_chunks_by_manifest, get_chunk_doc_id
from learning_rag.llm import complete
from learning_rag.ranks.term_overlap import top_k

RESULTS = Path(__file__).resolve().parent / "results"


def run_query(
    query: str,
    chunks: list[tuple[int, str]],
    *,
    with_answer: bool = False,
    only_free_model: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    hits = top_k(query, chunks, k=RANK_K)
    retrieval_ms = (time.perf_counter() - started) * 1000
    context = "\n\n".join(f"[start={start}] {text.strip()}" for _, start, text in hits[:PROMPT_K])
    prompt = (
        "Answer briefly from the context only. If the context does not say, reply exactly: I do not know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
    row: dict[str, Any] = {
        "question": query,
        "retrieval": [
            {"doc_id": get_chunk_doc_id(text), "score": score, "start": start, "text": text}
            for score, start, text in hits
        ],
        "retrieved": [get_chunk_doc_id(text) for _, _, text in hits],
        "context_doc_ids": [get_chunk_doc_id(text) for _, _, text in hits[:PROMPT_K]],
        "prompt": prompt,
        "answer": None,
        "answer_error": None,
        "generation": None,
        "retrieval_ms": round(retrieval_ms, 3),
        "e2e_ms": None,
    }
    if with_answer:
        try:
            result = complete(
                prompt, only_free_model, seed=SEED, temperature=TEMPERATURE,
                reasoning_effort=REASONING_EFFORT,
            )
            row["generation"] = result
            if not result["text"] or result["finish_reason"] != "stop":
                raise RuntimeError(f"incomplete model output: {result['finish_reason']}")
            row["answer"] = result["text"]
        except Exception as exc:
            row["answer_error"] = str(exc)
        row["e2e_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer", action="store_true")
    parser.add_argument("--free", action="store_true")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()
    query = " ".join(args.query)
    chunks = fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP)
    if not query:
        print(f"{len((CORPUS / 'MANIFEST.txt').read_text(encoding='utf-8').split())} docs  {len(chunks)} chunks")
        return
    config = run_config(args.answer, args.free)
    payload = {"config": config, **run_query(query, chunks, with_answer=args.answer, only_free_model=args.free)}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "last_run.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.answer:
        if payload["answer_error"]:
            raise SystemExit(payload["answer_error"])
        print(payload["answer"])
    else:
        for index, hit in enumerate(payload["retrieval"], 1):
            preview = " ".join(hit["text"].split())[:100]
            print(f"{index}  score={hit['score']:.3f}  {hit['doc_id']}  {preview}")


if __name__ == "__main__":
    main()
