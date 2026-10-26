---
name: github-delivery
description: >
  Commit messages and branch names for this repo. Use when writing a commit,
  naming a branch, splitting a change, or reviewing a proposed Git message.
  Read docs/commit-messages.md before composing the message.
---

# GitHub delivery

Follow [docs/commit-messages.md](../../../docs/commit-messages.md). This file is the short form. The linked sections are the rules.

This repo has no devlog step. Do not generate or require a development log in a commit.

## Header

```text
<type>(<optional-scope>)!: <description>
```

The description is lowercase imperative English, with no trailing period. Details go in the body. See [Commit header](../../../docs/commit-messages.md#commit-header) and [Description](../../../docs/commit-messages.md#description).

## Type and scope

Pick `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `build`, or `ci` from the user-visible change. Scope is optional lowercase kebab-case for one capability (`naive-rag`, `chunks`, `eval`). Omit repo-wide labels. See [Types](../../../docs/commit-messages.md#types) and [Scope](../../../docs/commit-messages.md#scope).

## Body and breaking changes

Add a body when the header is not enough. Use `!` only when callers must change, and state the old and new call in the body. See [Body](../../../docs/commit-messages.md#body) and [Breaking changes](../../../docs/commit-messages.md#breaking-changes).

## Split and branches

One header, one concern. If the change is too large for one header, split it into multiple commits. Create that series in order and push once. A baseline that cannot run in pieces stays one commit. Branches are `<category>/<capability>`, without tracker ids or names. See [One commit](../../../docs/commit-messages.md#one-commit), [Several commits, one push](../../../docs/commit-messages.md#several-commits-one-push), and [Branch names](../../../docs/commit-messages.md#branch-names).

## Leave out

No `RAG-9` in the header, no secrets, no devlog. See [What stays out](../../../docs/commit-messages.md#what-stays-out).
