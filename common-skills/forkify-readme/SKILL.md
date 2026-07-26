---
name: forkify-readme
description: Replace an upstream project's README with a concise README for a maintained fork, grounded in current fork-only behavior. Use when a user asks to forkify, rewrite, shorten, or give the same README treatment to a fork; when general documentation should move behind an upstream link; or when existing fork documentation must be reconciled with source, tests, history, and runtime behavior.
---

# Forkify README

## Goal

Turn a copied upstream README into a compact landing page for the fork. Link to
upstream for the general product documentation, summarize the fork's user-facing
changes, and expand those changes in focused sections backed by current evidence.

Treat the repository named by the user as the target. If no path is named, use
the current repository.

## Ground Rules

- Preserve unrelated and pre-existing work in the target checkout.
- Document current behavior, not an aspirational plan or chronological changelog.
- Treat old fork docs and commit messages as leads, not authorities.
- Cover user-visible fork differences; omit pure refactors, test-only changes,
  merge mechanics, and routine upstream changes.
- Keep exact option names, defaults, syntax, limitations, build requirements, and
  license terms.
- Edit only the README unless the user asks for related code or documentation
  changes.
- Do not merge, rebase, commit, or push unless the user separately requests it.

## Workflow

### 1. Establish the repository state

Read the repository instructions and existing root README first. Inspect any
`FORK.md`, changelog, development notes, manifests, and package metadata that can
identify the project, upstream URL, build requirements, and license.

Before editing, inspect:

```bash
git status --short --branch
git remote -v
git branch --show-current
```

Resolve the actual upstream remote and its default branch; do not assume the
remote is named `upstream` or the branch is `main` or `master`. If current remote
state matters and network access is allowed, fetch the upstream remote with
pruning. Fetching may update remote-tracking refs, but must not alter the branch
or worktree.

If the README already has uncommitted edits, identify which edits belong to the
user and preserve them. Stop for direction only when those edits cannot safely
be reconciled with the requested replacement.

### 2. Find the fork's actual delta

Set `upstream_ref` to the resolved remote-tracking branch and `fork_base` to its
merge base with `HEAD`, then inspect both history and content:

```bash
git rev-list --left-right --count HEAD..."$upstream_ref"
fork_base=$(git merge-base HEAD "$upstream_ref")
git log --oneline --decorate "$upstream_ref"..HEAD
git diff --stat "$fork_base" HEAD
git diff --name-status "$fork_base" HEAD
git diff --stat "$upstream_ref" HEAD
```

Use the merge-base diff to seed the candidate inventory. Use the final direct
tree comparison only to understand how the current fork differs from current
upstream. When the fork is behind upstream, the direct comparison also contains
newer upstream work absent from the fork; never describe that upstream-only work
as a fork change. Use the divergence count, fork-side commits, blame/history,
and current implementation together to separate local features from upstream
drift.

Search likely evidence surfaces, including:

- public CLI or API definitions;
- source implementing changed behavior;
- focused tests and fixtures;
- generated help, manpages, completions, or schemas;
- fork notes and development plans; and
- current package metadata.

Build an internal inventory with one row per candidate feature: its user-facing
contract, confirming source/tests, a possible runtime probe, and whether it is
current. Drop candidates that are internal, removed, stale, or not actually
different from upstream.

### 3. Resolve claims from strongest evidence

Prefer evidence in this order:

1. Current checkout-built runtime behavior together with source or tests
2. Current source implementation
3. Focused tests and fixtures
4. Current package or build metadata
5. Existing fork documentation
6. Commit messages and plans

Use old documentation to locate features, then correct it when it disagrees with
the implementation. Verify exact spellings, case sensitivity, defaults,
precedence, aliases, platform behavior, boundary cases, and known limitations.
Do not silently change source code merely to make a documentation claim true.

### 4. Compose the fork README

Use this shape unless the repository calls for a small adaptation:

```markdown
# a <project> fork

This is a fork of <project>. <One-sentence description of the project>. See the
[upstream repository](https://example.com/owner/project) for full documentation.

## about this fork

This fork <accurate relationship to upstream> and adds:

- <short user-facing difference>;
- <short user-facing difference>; and
- <short user-facing difference>.

Everything else behaves like upstream <project> unless noted below.

### <major fork feature>

<Verified behavior, examples, defaults, and important limitations.>

### <another fork feature>

<Verified behavior, examples, defaults, and important limitations.>

## building

<Verified minimum toolchain and shortest useful build command.>

## license

<Verified license statement.>
```

Choose `a` or `an` naturally. Derive the one-sentence project description from
current authoritative project metadata or upstream text without reproducing the
upstream feature tour.

Make the overview bullets a quick gloss. Let the breakout sections provide the
details instead of repeating the same prose. Order sections by importance to a
fork user, not by commit date. Include command examples when they clarify the
interface, and state meaningful limitations beside the feature they constrain.

Include building and license sections only after checking current metadata. Say
that the fork tracks or regularly merges upstream only when history supports the
claim. If broad compatibility has not been established, omit or narrow
"Everything else behaves like upstream."

Avoid:

- copying upstream badges, installation tours, screenshots, benchmarks, or
  exhaustive option references;
- presenting every fork commit as a feature;
- documenting experimental plans as shipped behavior;
- claiming an installed global binary represents the checkout; and
- embedding volatile commit counts, hashes, or dates unless they are directly
  useful to readers.

### 5. Verify the finished README

Read the complete rendered source once for structure, repetition, stale names,
placeholder text, and broken local references. Then validate in proportion to a
documentation-only change:

- Run safe, focused examples against a binary or artifact built from the target
  checkout. Prefer a temporary fixture over scanning unrelated user data.
- Exercise parsers or mini-help for compact syntaxes and edge cases described in
  the README.
- Use focused tests when runtime probes are impractical. Do not run a full suite
  solely because the README changed unless repository instructions require it.
- Run the repository's Markdown checks when present.
- Run `git diff --check`, inspect the complete README diff, and confirm that only
  expected files changed.
- Search for `TODO`, `FIXME`, placeholder links, obsolete feature names, and
  claims inherited from stale docs.

If an example cannot be exercised, say exactly which evidence supports it and
which validation was not run.

## Completion Report

Report the README path, the fork-specific areas it now covers, the checks that
passed, and any deliberate validation boundary. Mention other modified files
only when they were part of the requested work.
