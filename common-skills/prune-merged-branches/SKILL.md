---
name: prune-merged-branches
description: Delete fully merged local and remote branches within one selected remote, with or without pull requests. Use for routine branch cleanup after merging into the default branch, including same-repository squash/rebase PR merges. Excludes cross-fork PR cleanup and cross-remote comparisons or operations.
---

# Prune Merged Branches

Clean up branches whose complete tips have been merged into the selected remote's default branch. A request to clean up or delete merged branches authorizes qualifying deletions; do not add a routine confirmation gate. For a preview or assessment request, report candidates without deleting them. Common exclusions are normal skips, not reasons to interrupt the user. Use judgment to pause and ask about unusual or unexpected situations.

## Select one remote and default branch

1. Inspect the repository, local branch configuration, and linked worktrees:

   ```bash
   git status --short --branch
   git remote
   git worktree list --porcelain
   git for-each-ref --format='%(refname)%09%(objectname)%09%(upstream)%09%(upstream:remotename)%09%(upstream:remoteref)' refs/heads/
   ```

2. Select the sole remote when there is one. With multiple remotes, select `origin` if present. With multiple remotes and no `origin`, tell the user the remote names and wait for their instruction. With no remotes, report that nothing qualifies and stop.
3. Set `remote` to that exact name. Inspect only its fetch and push URLs (`git remote get-url --all "$remote"` and `git remote get-url --push --all "$remote"`). Establish that fetching and pushing address the same repository. Different URL transports are fine; different repositories, multiple push destinations, or mirror configuration require clarification before proceeding.
4. Discover the remote's default from `git ls-remote --symref "$remote" HEAD`. If its HEAD does not identify a branch, use that repository's hosting metadata. Do not guess from the current branch, a stale local remote HEAD, or the presence of `main`/`master`. Ask if the default cannot be established unambiguously.
5. Refresh branch refs only, without fetching other remotes, tags, or submodules:

   ```bash
   git fetch --no-tags --no-prune-tags --prune --no-recurse-submodules "$remote" \
     "+refs/heads/*:refs/remotes/$remote/*"
   git ls-remote --heads "$remote"
   ```

   Set `default_branch` to the discovered name and resolve `refs/remotes/$remote/$default_branch` to `default_oid`. Stop if the fetch fails or the default ref is missing. Compare against this fetched tip, not the local default branch. In a shallow repository, obtain enough history from this remote to prove ancestry or skip inconclusive candidates.

Never fetch, query PRs from, compare against, or modify another remote. Local configuration may be read to exclude branches associated with other remotes. Cross-fork workflows belong to `prune-merged-fork-branches`; do not run that workflow as part of this skill.

## Inventory and exclusions

Consider all live branches on the selected remote, including remote-only branches, plus local branches associated with it:

- A configured upstream on this remote establishes association even if that upstream branch has already been deleted. Preserve this mapping when pruning stale remote-tracking refs; upstream names can differ from local names.
- With no configured upstream, a live same-named branch on this remote establishes association. Name matching establishes association only, not merge status.
- Skip local branches with no such association, with a local-only upstream, or with an upstream on another remote. Do not substitute a same-named branch for an explicitly configured different upstream.

Exclude the following before considering merge proof:

- The discovered default branch and the exact names `main`, `master`, `develop`, `development`, and `trunk`.
- Additional branches protected by repository instructions or hosting rules. On GitHub, inspect the selected repository's protected branches (including ruleset protection) with a paginated branches API query. If protection information cannot be obtained, disclose the limitation and conservatively skip refs whose protection status is uncertain. Never override a server protection rejection.
- Every branch checked out in any worktree. Exclude its local ref, same-named remote ref, and configured upstream on this remote. Apply the same association mapping to protected branches so a differently named local tracking branch cannot bypass protection.

Do not switch branches, remove worktrees, stash, reset, merge, or rebase to make cleanup possible. Dirty files alone do not prevent deleting other eligible refs.

## Prove each tip is merged

Evaluate local and remote refs independently. An eligible remote tip does not establish that a local tip with extra commits is safe, and the reverse is also true. Use either of these proofs:

### Git ancestry (PR or non-PR)

```bash
git merge-base --is-ancestor "$candidate_oid" "$default_oid"
```

Exit 0 proves the complete candidate tip is contained in the default history; exit 1 means it is not. Other errors are failed checks, not evidence. This works without a hosting API. Skip unmerged and partially merged refs unless the PR proof below covers the exact tip. Patch similarity, matching trees, and a branch's name are not merge proof.

### Same-repository PR evidence (squash/rebase)

On GitHub, use `gh` against the selected repository explicitly, including its hostname for GitHub Enterprise. Derive the repository from the selected remote rather than relying on `gh`'s implicit repository selection. For other hosts or unavailable PR metadata, keep ancestry-based cleanup and report which refs lack sufficient evidence.

List closed PRs targeting the default branch with pagination, then inspect promising PRs individually. For example, with `host` and `repo` set to the selected host and `OWNER/REPO`:

```bash
gh api --hostname "$host" --method GET --paginate "repos/$repo/pulls" \
  -f state=closed -f base="$default_branch" -f per_page=100
gh api --hostname "$host" "repos/$repo/pulls/$number"
```

Require all of the following from the PR details:

- `merged` is true and `merged_at` is present; a closed PR alone is insufficient.
- `head.repo` and `base.repo` both identify the selected repository. Exclude cross-fork PRs without inspecting the other repository. Missing identity is insufficient evidence.
- `base.ref` equals `default_branch`, and `head.ref` matches the candidate's associated remote branch name.
- The PR's recorded `head.sha` equals the candidate's current full object ID. An old merged PR for a reused name, or new commits after the merge, does not qualify. Check the local and remote IDs separately.
- `merge_commit_sha` is present and is an ancestor of `default_oid`. For squash/rebase merges, this is the resulting commit recorded by GitHub. If the object is missing, try obtaining it from the selected remote only; otherwise skip this proof.

Do not fall back to looser checks when metadata is missing or contradicts the candidate. Ancestry proof remains independently sufficient. See the [GitHub PR API](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request) for the recorded head and merge result fields.

## Delete and verify

Record each qualifying ref's full name, tip SHA, association, and merge evidence (default SHA or PR number/URL and merge SHA). Keep local and remote eligibility separate. For preview requests, stop with this inventory and skip reasons.

Before deletion, recheck the default tip, candidate tips, exclusions, and worktrees. If the default has changed, refresh and recompute proof; if a candidate has changed, skip it or reassess its new tip. Never reuse old evidence for a new tip.

Delete qualifying remote refs first, one ref at a time, using the exact inspected SHA as a lease:

```bash
git push --no-follow-tags --recurse-submodules=no \
  --force-with-lease="refs/heads/$remote_branch:$remote_oid" \
  "$remote" ":refs/heads/$remote_branch"
```

The explicit lease prevents deleting a remote branch that advanced since inspection. Do not use plain `--force`, an implicit lease, wildcard deletion, or an unqualified default push. See [Git's lease documentation](https://git-scm.com/docs/git-push).

If remote deletion fails, preserve its corresponding local branch and report the failure. Do not retry with weaker protection. If another actor already removed the remote branch, verify that exact ref is absent; a separately eligible local branch may still be deleted. Remote refs skipped because they contain unmerged commits do not invalidate independent proof for an older local tip.

Immediately before each local deletion, recheck its exact SHA and all worktree checkouts. Try `git branch -d -- "$local_branch"`. If it refuses only because its merge check uses an unsuitable upstream/HEAD (including a gone upstream, stale local default, or squash/rebase history), `git branch -D -- "$local_branch"` is allowed after reconfirming the independent proof and exclusions. Do not force past unexpected errors or worktree protection.

Refresh and prune only the selected remote's branch refs using the fetch command above. Verify the exact deleted remote refs are absent with `git ls-remote --heads "$remote" "refs/heads/$remote_branch"` and the local refs are absent with `git show-ref --verify --quiet "refs/heads/$local_branch"` (exit 1 means absent). Distinguish a failed query from an absent ref; report any concurrent recreation rather than deleting it again automatically.

Report the selected remote/default, deleted local and remote branches, skipped refs with concise reasons, and any failures. Include PR links for PR-based proof and retain the recorded tip SHAs in the operation report so the affected commits remain identifiable. An empty candidate set is a successful no-op.
