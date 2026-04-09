---
name: git-content-equivalence
description: Use when a user needs help reconciling Git histories that look deeply diverged because of rebases, filter-repo runs, author or metadata rewrites, or force-pushes, but whose file content is mostly the same. Helps determine naive ancestry divergence vs content-equivalent divergence, map rewritten commits by patch equivalence, and recommend a smart replay strategy instead of a naive merge.
---

# Git Content Equivalence

Use this skill when branch or repo history may have been rewritten, so commit IDs diverge much earlier than the meaningful file-content divergence.

Core terms:

- `naive divergence`: where commit ancestry first differs by commit ID / merge-base.
- `content-equivalent`: two commits with the same tree content, even if commit IDs, parents, authors, or dates differ.
- `patch-equivalent`: two commits that Git considers the same change even if metadata differs.
- `smart replay`: apply only the real content delta after the content-equivalent point, instead of merging whole rewritten histories.

## Goals

1. Tell the user whether this is mostly a metadata rewrite or a real content divergence.
2. Identify the latest content-equivalent point between the histories.
3. Isolate the real content delta after that point.
4. Recommend a safe reconciliation strategy.

## Workflow

### 1. Inspect ancestry and reflog

Use reflog first if the user mentions a recent fetch, reset, force-push, rebase, or filter-repo event.

Useful commands:

```bash
git reflog --date=local -20
git reflog show origin/main --date=local -20
git log --oneline --decorate --graph --all -20
git merge-base <left> <right>
```

Interpretation:

- A `fetch: forced-update` or similar reflog entry strongly suggests rewritten history.
- A very old merge base does not by itself mean the content really diverged that early.

### 2. Compare histories by patch identity, not only ancestry

Use `range-diff` when the histories are plausibly “same series, rewritten”.

```bash
git range-diff <base>..<old_tip> <base>..<new_tip>
git cherry <old_tip> <new_tip>
```

Interpretation:

- `range-diff` is best for commit-to-commit mapping across rewritten history.
- `git cherry` marks patch-equivalent commits with `-` and truly new content with `+`.
- If almost everything is `-` and only a few commits are `+`, this is mostly a metadata rewrite plus a small real delta.

### 3. Compare tree content directly

Check whether tips or intermediate commits have identical tree hashes.

```bash
git rev-parse <commit>^{tree}
git log --reverse --format='%H %T %s' --first-parent <branch>
```

Interpretation:

- Equal tree hashes mean equal file content for that commit.
- If old tip tree == some rewritten-history commit tree, that rewritten commit is the content-equivalent match for the old tip.

When comparing two repos or branches, find:

1. the naive ancestry divergence point
2. the latest content-equivalent commit pair
3. the real content delta after that pair

### 4. Summarize for the user in plain language

State both divergence notions explicitly:

- “The commit graph diverged at `<commit>`.”
- “But file content stayed aligned through `<old_commit>` / `<new_commit>`.”
- “The real content difference is only `<new_equivalent>.. <new_tip>`.”

If this is a metadata rewrite, say so directly.

## Recommended reconciliation strategies

Prefer the smallest content-preserving operation.

### Case A: Old tip is content-equivalent to a rewritten commit, and new history has extra real commits

This is the cleanest case.

Options:

- Replay the truly new commit(s):

```bash
git cherry-pick <new_commit>
```

- Or apply the net diff from the content-equivalent point:

```bash
git diff <new_equivalent>..<new_tip> | git apply -3
git commit
```

Avoid a naive merge of the two branch graphs.

### Case B: User wants a comparison copy of the pre-rewrite state

Use reflog commit IDs to restore another checkout or branch to the old tip:

```bash
git reset --hard <old_tip>
git update-ref refs/remotes/origin/main <old_tip>
```

Only do this in a comparison clone or when the user clearly wants that repo state recreated.

### Case C: Worktree contains a manual rollback of rewritten content

If unstaged edits reconstruct the old tree on top of rewritten history, explain that this is not a true merge resolution. It is a manual back-port / rollback overlay.

Recommend:

1. restore the rewritten branch to clean state
2. identify the content-equivalent match
3. replay only the real delta wanted from either side

## Preferred phrasing

Use these terms consistently:

- `naive merge-base`
- `content-equivalent tip`
- `patch-equivalent history`
- `metadata rewrite`
- `real content delta`
- `smart replay`

This helps users understand why “deep divergence” in commit history may still correspond to a very small content difference.

## Output checklist

When answering, include:

1. the naive ancestry divergence point
2. the latest content-equivalent commit pair
3. whether the mismatch is mostly metadata rewrite vs real code/content drift
4. the minimal replay or reconciliation command sequence
5. any safety warning if the proposed command rewrites refs or discards worktree changes
