---
name: prune-merged-fork-branches
description: Delete local and remote fork branches that were merged upstream through pull requests. Use when a repo has an `origin` fork feeding dedicated feature branches into an `upstream` repository, and merged-branch cleanup should be determined from GitHub PR history via `gh` rather than `git --merged` ancestry or exact-superset logic.
---

# Prune Merged Fork Branches

## Overview

Use GitHub PR metadata as the source of truth for cleanup when fork feature branches are merged upstream by squash, rebase, or other non-ancestry-preserving methods. Delete only branches whose PRs are merged upstream and whose head repository is the fork being pruned.

## Assumptions

- The current checkout has a fork remote, usually `origin`, and an upstream remote, usually `upstream`.
- Feature branches live on the fork and are submitted as PR heads to the upstream repo.
- The user wants branches removed from both the fork remote and local refs when present.
- Branch merged status must come from upstream PR state, not from whether branch tips are ancestors of `upstream/main`.

## Workflow

### 1. Confirm context

Identify the fork and upstream repos from remotes unless the user specifies them explicitly.

```bash
which gh
gh auth status
git status --short --branch
git remote -v
git worktree list --porcelain
```

Do not proceed if the repo/remotes are ambiguous. Do not delete a branch that is checked out in any worktree.

### 2. Refresh refs

Prune before inventorying so stale tracking refs do not become candidates.

```bash
git fetch upstream --prune
git fetch origin --prune
```

### 3. Compute candidates from PR metadata

Use the upstream repo's merged PR list, filter to PRs whose head repository is the fork, then intersect those PR head names with current fork remote heads and local branches.

Set these for the actual repo:

```bash
upstream_repo="OWNER/REPO"
fork_owner_repo="FORK_OWNER/REPO"
fork_remote="origin"
```

Then compute candidates:

```bash
prs_json=$(gh pr list \
  --repo "$upstream_repo" \
  --state merged \
  --limit 1000 \
  --json number,title,headRefName,headRepository,mergedAt,url)

remote_json=$(git ls-remote --heads "$fork_remote" \
  | awk '{ sub("refs/heads/", "", $2); print $2 }' \
  | jq -Rsc 'split("\n")[:-1]')

local_json=$(git for-each-ref --format='%(refname:short)' refs/heads \
  | jq -Rsc 'split("\n")[:-1]')

printf '%s' "$prs_json" | jq -r \
  --arg fork_owner_repo "$fork_owner_repo" \
  --argjson remote "$remote_json" \
  --argjson local "$local_json" '
    map(select(.headRepository.nameWithOwner == $fork_owner_repo))
    | map(.headRefName as $b | . + {
        remoteExists: ($remote | index($b) != null),
        localExists: ($local | index($b) != null)
      })
    | map(select(.remoteExists or .localExists))
    | sort_by(.headRefName)
    | .[]
    | [
        .headRefName,
        ("#" + (.number | tostring)),
        .mergedAt,
        (if .remoteExists then "remote" else "-" end),
        (if .localExists then "local" else "-" end),
        .title
      ]
    | @tsv
  '
```

Bind `.headRefName as $b` before membership checks. Without that binding, `jq` may switch `.` to the candidate array and fail or compare the wrong value.

### 4. Delete and verify

If candidates exist and the user asked for deletion, delete the remote branches first, prune, then delete local branches. Use `git branch -D` for local refs because PR-merged squash/rebase branches may not be ancestry-merged into the local base.

```bash
git push "$fork_remote" --delete <branch...>
git fetch "$fork_remote" --prune
git branch -D <branch...>
```

Verify exact refs are gone:

```bash
git ls-remote --heads "$fork_remote" <branch...>
git for-each-ref --format='%(refname:short)' refs/heads/<branch> ...
```

Rerun the PR/ref intersection query. It should return no rows for branches that are both merged upstream and still present locally or on the fork remote.

## Safety Rules

- Treat `gh pr list --repo <upstream> --state merged` as the authority for merged PR status.
- Filter by `headRepository.nameWithOwner == <fork owner/repo>` so similarly named upstream or third-party branches are not deleted.
- Intersect with live `git ls-remote --heads <fork remote>` before deleting remote refs.
- Check linked worktrees before local deletion.
- Do not rely on `git --merged`, `git branch --merged`, or exact branch-tip ancestry as the cleanup authority for this workflow.
- Report PR numbers, merge timestamps, and branch names in the final summary.
