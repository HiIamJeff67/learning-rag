import argparse
import json
from pathlib import Path
import sys

from .chunk import STRATEGIES, ChunkSpec
from .eval import compare
from .index import delete_source, search_index, sync_index


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data/raw/peps"
QUESTIONS = ROOT / "datasets/eval_questions.csv"
RESULTS = Path(__file__).resolve().parent / "results"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="RAG-10 document ingestion and chunk comparison")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--corpus", type=Path, default=CORPUS)
    ingest.add_argument("--index", type=Path, required=True)
    ingest.add_argument("--strategy", choices=STRATEGIES, default="section")
    ingest.add_argument("--size", type=int, default=500)
    ingest.add_argument("--overlap", type=int, default=0)
    ingest.add_argument("--prune", action="store_true", help="remove sources missing from this corpus")
    search = commands.add_parser("search")
    search.add_argument("--index", type=Path, required=True)
    search.add_argument("--k", type=int, default=5)
    search.add_argument("query")
    delete = commands.add_parser("delete")
    delete.add_argument("--index", type=Path, required=True)
    delete.add_argument("source_id")
    evaluate = commands.add_parser("compare")
    evaluate.add_argument("--corpus", type=Path, default=CORPUS)
    evaluate.add_argument("--questions", type=Path, default=QUESTIONS)
    evaluate.add_argument("--output", type=Path, default=RESULTS)
    args = parser.parse_args()
    try:
        if args.command == "ingest":
            spec = ChunkSpec(args.strategy, args.size, args.overlap)
            result = sync_index(args.index, args.corpus, spec, prune=args.prune)
        elif args.command == "search":
            result = search_index(args.index, args.query, args.k)
        elif args.command == "delete":
            result = {"source_id": args.source_id, "deleted": delete_source(args.index, args.source_id)}
        else:
            result = compare(args.corpus, args.questions, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
