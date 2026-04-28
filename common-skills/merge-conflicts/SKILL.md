---
name: merge-conflicts
description: Use when the user invokes the skill.
---

# Merge Conflict Resolution

Resolve git merge conflicts by examining all three versions (base, ours, theirs) and the commit history for each conflicted file, then making informed resolutions.

## Prerequisites

You MUST be in a merge-conflicted state (`git status` shows "Unmerged paths").
If not, tell the user and stop.

## Workflow

### Phase 1: Assess

1. List conflicted files:
   ```bash
   git diff --name-only --diff-filter=U
   ```

2. Get the merge context (what triggered this):
   ```bash
   # What are we merging?
   git log --oneline -1 HEAD         # ours
   git log --oneline -1 MERGE_HEAD   # theirs (or REBASE_HEAD / CHERRY_PICK_HEAD)
   ```

### Phase 2: Analyze each conflicted file

For EACH conflicted file, gather three inputs:

1. **Re-checkout with diff3 markers** (shows base between `|||||||` and `=======`):
   ```bash
   git checkout --conflict=diff3 -- <file>
   ```
   Then read the conflict regions in the working copy. This is the primary input — it shows what the original code was and how each side changed it.

2. **Commit-level context** — which commits on each side touched this file and why:
   ```bash
   git log --oneline --left-right --merge -- <file>
   ```
   Use `-p` if the commit list is short (< ~5 commits) for full diffs.

3. **Local fork history** — if the repo has both `origin` (fork) and `upstream` remotes, check what local work touched the conflicted areas:
   ```bash
   git log --oneline origin/main..HEAD -- <file>
   ```

### Phase 3: Resolve

For each conflict region, determine the correct resolution by understanding the **intent** of each side:

- If one side added code and the other didn't touch that area: **keep the addition**
- If one side deleted code and the other modified it: **understand why it was deleted** (was the feature removed upstream? was it refactored elsewhere?) before deciding
- If both sides modified the same code differently: **combine the intents** — don't just pick a side unless one is clearly superseded
- If one side is a pure refactor/rename and the other is a feature change: **apply the feature change using the refactored form**

Use the Edit tool to replace conflict markers with the resolved code. Do NOT leave any `<<<<<<<`, `=======`, or `>>>>>>>` markers.

### Phase 4: Verify and complete

1. Confirm no conflict markers remain:
   ```bash
   grep -rn '<<<<<<< \|======= \|>>>>>>>' <file>
   ```

2. Stage resolved files:
   ```bash
   git add <file1> <file2> ...
   ```

3. Complete the merge:
   ```bash
   git commit --no-edit
   ```

## Important notes

- ALWAYS use `git checkout --conflict=diff3` before analyzing — the default 2-way markers lose critical information about what the base looked like.
- When extracting individual versions for deeper analysis, use index stages:
  - `git show :1:<file>` — base (common ancestor)
  - `git show :2:<file>` — ours (HEAD)
  - `git show :3:<file>` — theirs (MERGE_HEAD)
- For large files, use `git show :N:<file>` to read specific versions rather than trying to parse interleaved diff3 markers in a huge file.
- Prefer understanding intent over mechanical resolution. Read commit messages.
- Use `$TMPDIR` (not `/tmp`) for any temporary files.
