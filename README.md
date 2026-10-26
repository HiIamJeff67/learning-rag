# learning-rag

A shared repo for learning RAG by running the same corpus through each technique and comparing the results.

Two people work through the same experiments. Notes from a study session go in `notebook/`. Source papers and links go in `textbook/`. Each technique gets a directory under `experiments/` with a hypothesis, a fixed dataset, and a way to rerun it.

## Setup

Install [uv](https://docs.astral.sh/uv/), then from the repo root:

```bash
uv sync --group dev
```

This creates `.venv`, installs the project, and installs pytest. Later commands use that environment through `uv run`.

```bash
uv run pytest
uv run python -m experiments.e01_naive_rag.run
uv run python -m experiments.e01_naive_rag.run "What is a docstring?"
```

Copy `.env.example` to `.env` when an experiment needs an API key. The term-overlap experiment does not.

## Where things go

| Path | Contents |
|---|---|
| `data/raw/` | Corpus files. The current pin is in `data/raw/SOURCE.txt`. |
| `experiments/` | One directory per learning item. `run.py` wires the shared functions for that item. |
| `src/learning_rag/` | Shared functions in capability packages such as `chunks/` and `ranks/`. |
| `tests/` | Integration tests and tests that cross package boundaries. |
| `notebook/` | Study notes for the current chapter. |
| `textbook/` | Papers and reading links. |
| `datasets/` | Question sets with expected document ids. |

## Current experiment

`experiments/e01_naive_rag/` is the RAG-9 baseline: fixed-size chunks of PEP 257, term-overlap cosine, and an optional text-model answer. The corpus commit is recorded in `data/raw/SOURCE.txt`. Changing those files means pinning a new source and rerunning the experiment.
