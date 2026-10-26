---
name: coding-style-and-convention
description: >
  Coding rules for this repo: one installable package under src/learning_rag,
  experiments as the runnable unit, no one-off helpers, naming, types, and
  tests. Use when writing, moving, reviewing, or explaining Python in
  learning-rag.
---

# Coding style and convention

Follow this when changing Python, layout, or experiment wiring in this repo. The live tree wins over a diagram. `.agents/architecture.md` sections 5–7 are the plan for experiments and evaluation; do not create directories or files just because that diagram lists them.

## One package

This is one installable package, the usual Python src layout. The repo root is the project root. `src/` is not a second project, and it is not part of the import name.

- Import `learning_rag`. The distribution name `learning-rag` is only for packaging.
- A wheel contains `learning_rag/`, not `src/`.
- Do not add another top-level package under `src/` (`src/basic/`, `src/graph_rag/`, `src/util/`). A new technique is an experiment, not a new package.
- Do not use uv workspaces unless two experiments need different dependency sets.
- Do not add a dependency for a few lines the standard library already covers.

## Where code goes

`src/learning_rag/` holds a function only after a second caller imports it. Until then it stays in the experiment that uses it.

| Path | Put it here |
|---|---|
| `src/learning_rag/chunks/`, `ranks/` | Reused chunkers and rankers. One implementation per file: `chunks/fixed.py`, `ranks/term_overlap.py`. |
| `src/learning_rag/llm.py`, `metrics.py` | Reused generation and scoring. |
| `src/learning_rag/shared/settings.py` | Process config: `.env`, model, token ceilings. |
| `experiments/NN_name/` | One technique: hypothesis, wiring, constants, prompt, results. |
| `data/`, `datasets/`, `notebook/`, `textbook/` | Corpus, question sets, notes, papers. Never inside `src/`. |
| `tests/` | Tests that cross package boundaries. |

`experiments/NN_name/run.py` calls the steps in order: load, chunk, retrieve, prompt, generate. Do not load another experiment with `importlib`. If the second experiment needs a function, move that function into `learning_rag` and import it.

Do not pre-build empty packages for a future chunker, ranker, or GraphRAG module.

## Helpers

Write a helper only when a second caller uses it, or when naming the step makes the surrounding function easier to check.

- Used once: put the code at the call site. Do not add `_post`, `_send`, or `build_prompt` for a single call.
- Used twice inside one implementation: it may stay in that file. Do not make a package for it.
- Used by two implementations in the same capability: a file in that capability (`chunks/common.py`), and only then.
- Used by two capabilities: a module named for the job (`text.py`), never `util/` or `helpers/`.
- A wrapper must change behavior (retry a 400, refuse a paid model, keep one cached config). A wrapper that only forwards arguments does not stay.
- Do not add a re-export in `__init__.py` unless a caller already needs the short import.

## Config

Read model settings in `get_config()`. Do not hardcode ceilings, model ids, or keys at the call.

- Env names: `MODEL_API_KEY`, `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_MAX_TOKENS`, `MODEL_REASONING_TOKENS`.
- Defaults live next to the read. Empty env values fall back to the default. Do not override variables already set in the process.
- A caller may pass `max_tokens` or `reasoning_tokens` into `complete()` to override the config for that call.
- New env vars go in `.env.example`.
- `load_env_file` accepts `KEY=VALUE` only. Do not grow it into a dotenv clone unless a value needs comments or more than one line.

## Names

- Packages and modules: `snake_case`. Capability directories are plural when they hold variants (`chunks/`, `ranks/`).
- Functions say what they do: `fixed_chunks`, `top_k`, `complete`, `get_config`. Not `process`, `handle`, or `run_helper`.
- Experiments: `eNN_short_name`, numbered in learning order (`e01_naive_rag`). The number is not a version. The name must be a Python identifier so it can be a package. `experiments/` has no `__init__.py`. Run from the repo root with `uv run python -m experiments.e01_naive_rag.run`. Imports between files in that directory are relative (`from .config import`).
- Tests: `test_<module>.py` beside the module. Test names state the behavior (`test_bad_overlap`).
- Comments only for a reason the code cannot show. A known limit uses `shortcut: <limit>, <when to upgrade>`.

## Types and checks

- No bare `dict`, `list`, or `tuple` in annotations. JSON is `dict[str, Any]`.
- If an API returns `T | None`, narrow it before use. Do not pass the union into a function that requires `T`.
- Validate at the boundary: missing key, bad chunk size, non-free model when `--free` is set. Do not validate the same fact again in every helper.

## Experiments and evaluation

An experiment README states hypothesis, baseline, variables, dataset, metrics, and result. Do not claim a technique is better without a comparison on the same corpus and the same question set.

Shared scoring goes in `metrics.py` once two experiments need it. Do not edit the question set mid-experiment. If it must change, copy a new version and rerun the baseline.

When adding an experiment, copy the shape in `.agents/architecture.md` section 6. Skip files the run does not need (`config.yaml`, a notebook, `results/` before there is a result).
