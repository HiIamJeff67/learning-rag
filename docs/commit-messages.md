# Commit messages

Rules for commit headers, bodies, and branch names in this repository. There is no generated devlog step.

## Commit header

A commit header is one line:

```text
<type>(<optional-scope>)!: <description>
```

The scope and the `!` are optional. Parentheses appear only when a scope is present.

```text
feat(naive-rag): add a reproducible baseline on pinned peps
fix(eval): require every expected document in recall
docs: describe the commit header format
```

Incorrect headers:

```text
Added the baseline
feat: Added the baseline
feat(naive-rag): add a reproducible baseline on pinned peps.
FEAT(naive-rag): add a reproducible baseline
feat(RAG): add a reproducible baseline
RAG-9: add a reproducible baseline
```

The description has no trailing period. The type is lowercase. A tracker id such as `RAG-9` stays out of the header.

## Types

Use the type that matches the user-visible change, not the files touched.

| Type | Use when the change |
|---|---|
| `feat` | Adds or changes behavior a learner or caller can run |
| `fix` | Corrects behavior that was wrong |
| `refactor` | Moves or reshapes code without changing behavior |
| `docs` | Changes documentation only |
| `test` | Adds or changes tests only |
| `chore` | Updates ignore rules, lockfiles, or other housekeeping |
| `build` | Changes packaging or the installable project metadata |
| `ci` | Changes automation that runs outside a local `uv run` |

Examples:

```text
feat(ranks): rank chunks by term-overlap cosine
fix(llm): leave room for an answer after reasoning tokens
refactor(settings): read model config once per process
docs(commit-messages): add header and body examples
test(metrics): cover an empty percentile input
chore: ignore the local env file
build: record pytest in the dev dependency group
```

A change that adds a ranker and the test for that ranker is `feat`. A change that only adds tests for existing behavior is `test`. A rename that callers must update is `refactor` with `!` if the old import path stops working.

## Scope

The scope is optional. When present, it is lowercase kebab-case and names the capability that changed.

Good scopes in this repo: `naive-rag`, `chunks`, `ranks`, `eval`, `corpus`, `settings`, `llm`.

A scope is omitted when the change is not tied to one capability:

```text
chore: ignore the local env file
docs: describe the commit header format
```

These scopes add nothing, because the repository already supplies that context:

```text
feat(learning-rag): add a baseline
feat(backend): add a ranker
feat(rag): add a baseline
```

## Description

The description is lowercase English, imperative, and specific enough to recognize the change without opening the diff.

```text
feat(corpus): pin the first 100 python peps
fix(eval): exclude no-answer questions from recall
refactor(naive-rag): read chunk size from the experiment config
```

Too vague:

```text
feat(naive-rag): update code
fix(eval): fixes
chore: stuff
```

The first line stays short. Put file lists, numbers, and rationale in the body.

## Body

Leave the body empty when the header is the whole story. Add a body when a reader needs the reason, the limit, or how to rerun.

Separate the header and the body with one blank line. Wrap the body by clause, not by a fixed column.

```text
feat(naive-rag): add a reproducible baseline on pinned peps

The corpus pin, term-overlap retrieval, free-model generation, and the
30-question eval are one baseline. Recall and MRR ignore no-answer
questions. End-to-end latency includes generation.
```

```text
fix(llm): retry when a free model spends the token cap on reasoning

A :free model can return an empty content field when reasoning uses the
whole max_tokens budget. The call caps reasoning and retries once.
```

The body states what is true after the commit. It does not narrate the review conversation.

## Breaking changes

Add `!` after the scope, or after the type when there is no scope, only when existing callers must change.

```text
refactor(chunks)!: rename fixed_chunks_by_manifest
```

Explain the old call and the new call in the body:

```text
refactor(chunks)!: rename fixed_chunks_by_manifest

Callers used fixed_chunks_by_manifest. The function is now
chunks_from_manifest.
```

A new experiment, a new question row, or a new result file is not a breaking change.

## One commit

One commit is one concern that can be described by one header.

This baseline belongs in one commit, because the program, the question set, and the recorded scores are the same result:

```text
feat(naive-rag): add a reproducible baseline on pinned peps
```

Split only when each commit is understandable alone:

```text
feat(corpus): pin the first 100 python peps
feat(ranks): rank chunks by term-overlap cosine
test(eval): score recall and mrr on the pinned question set
```

A split that leaves the package unable to import, or the eval unable to find its questions, is too small.

## Several commits, one push

When the working tree is too large for one header, split it into several commits and push that series together. A delivery is the push, not a single commit.

Each commit in the series still has its own header and still stands alone. The last commit in the series is the one that leaves the branch in the state you intend to share. Do not push the first commit and leave the rest uncommitted.

```text
feat(corpus): pin the first 100 python peps
feat(ranks): rank chunks by term-overlap cosine
test(eval): score recall and mrr on the pinned question set
```

Those three commits are one delivery: create them in order, then push once.

```text
git push origin feature/naive-rag-baseline
```

A change that cannot be described except as one baseline stays one commit, even if the diff is large. Size alone is not a reason to split. A header that would have to say "and" is a reason to split.

## Branch names

Use `<category>/<capability>`. The capability is lowercase kebab-case and readable without a ticket.

Categories match commit types: `feature`, `refactor`, `fix`, `docs`, `test`, `build`, `ci`, `chore`.

```text
feature/naive-rag-baseline
fix/free-model-empty-content
docs/commit-messages
```

Branch names omit contributor names, agent names, and tracker ids such as `RAG-9`.

## What stays out

This repository has no devlog generator and no required log file in a commit.

Commit headers and branch names omit:

- tracker ids (`RAG-9`, `ENG-42`)
- contributor or agent names
- repository-wide labels (`learning-rag`, `backend`, `frontend`)

Secrets from `.env` never appear in a message, a diff, or a result file.
