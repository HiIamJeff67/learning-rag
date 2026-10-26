import io
import json
import sys
from pathlib import Path
from typing import Any

from .config import CHUNK_OVERLAP, CHUNK_SIZE, CORPUS, PROMPT_K, RANK_K, SETTINGS
from learning_rag.chunks.fixed import fixed_chunks_by_manifest
from learning_rag.llm import complete
from learning_rag.ranks.term_overlap import top_k
from learning_rag.shared.settings import get_config

HERE = Path(__file__).resolve().parent


def answer(
    query: str, only_free_model: bool = False
) -> tuple[str, list[tuple[float, int, str]], str]:
    hits = top_k(query, fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP), k=PROMPT_K)
    context = "\n\n".join(f"[start={start}] {text.strip()}" for _, start, text in hits)
    prompt = (
        "Answer from the context only. If the context does not say, reply: I do not know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
    return complete(prompt, only_free_model), hits, prompt


def main() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    want_answer = "--answer" in args
    only_free_model = "--free" in args
    query = " ".join(arg for arg in args if arg not in {"--answer", "--free"})
    results = HERE / "results"
    results.mkdir(exist_ok=True)

    if not query:
        chunks = fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"{len((CORPUS / 'MANIFEST.txt').read_text(encoding='utf-8').split())} docs  {len(chunks)} chunks")
        for index, (start, text) in enumerate(chunks, 1):
            preview = " ".join(text.split())[:80]
            print(f"{index:02d}  start={start:<5}  len={len(text):<4}  {preview}")
        return
    if want_answer:
        _, base, model, _, _ = get_config(only_free_model)
        text, hits, prompt = answer(query, only_free_model)
        payload: dict[str, Any] = {
            "config": SETTINGS,
            "model": model,
            "base": base,
            "query": query,
            "retrieval": [
                {"score": score, "start": start, "text": chunk}
                for score, start, chunk in hits
            ],
            "prompt": prompt,
            "answer": text,
        }
        (results / "last_run.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"base: {base}")
        print(f"model: {model}")
        print(text)
        print("saved experiments/e01_naive_rag/results/last_run.json")
        return
    chunks = fixed_chunks_by_manifest(CORPUS, CHUNK_SIZE, CHUNK_OVERLAP)
    hits = top_k(query, chunks, k=RANK_K)
    payload = {
        "config": SETTINGS,
        "query": query,
        "retrieval": [
            {"score": score, "start": start, "text": chunk} for score, start, chunk in hits
        ],
    }
    (results / "last_run.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"query: {query}")
    for index, (score, start, text) in enumerate(hits, 1):
        preview = " ".join(text.split())[:90]
        print(f"{index}  score={score:.3f}  start={start:<5}  {preview}")


if __name__ == "__main__":
    main()
