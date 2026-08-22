---
name: stacked-pr
description: Reason about, create, review, and manage GitHub pull requests that depend on other pull-request branches. Covers linear stacked PRs, branch-relative "PR on a PR" workflows, competing alternative changes to an existing PR, review strategy, merge order, CI, forks, and common failure modes.
---

# Stacked PRs

Use this skill when a GitHub change is easier to understand, review, test, or collaborate on as multiple pull requests whose base branches are not all the repository's trunk branch.

This includes two related but distinct patterns:

1. **Linear stacked pull requests** — dependent changes form an ordered chain.
2. **PRs against a PR branch** — a collaborator proposes a change to an already-open PR. This can be linear, but competing proposals create a fan-out rather than a true GitHub stack.

The second pattern is especially useful when somebody reviewing a PR wants to say not merely *"I think this should be different"*, but *"here is a concrete, reviewable implementation of what I mean"* without pushing directly into the original author's branch.

## Core model

A normal PR is already a relationship between two branches:

```text
base branch  ←  head branch
main         ←  feature
```

A stacked PR simply uses another feature branch as the base of the next PR:

```text
main  ←  feature-a  ←  feature-b  ←  feature-c
         PR #101       PR #102       PR #103
```

The important consequence is that the diff for `feature-b` is computed against `feature-a`, not against `main`. Reviewers of PR #102 therefore see only the changes introduced by that layer.

GitHub's first-class **Stacked pull requests** feature formalizes the linear version of this model. As of August 2026 it is in public preview. GitHub defines a stack as a series of PRs in the same repository where each PR targets the branch of the PR immediately below it.

## Terminology

Use these terms precisely:

- **Trunk** — the base branch of the bottom PR in an official stack, often `main`, but it can be another long-lived branch such as `release`.
- **Base branch** — the branch a particular PR proposes to modify.
- **Head branch** — the branch containing the proposed changes.
- **Layer** — one PR/branch in a linear stack.
- **Stack** — a linear chain of dependent PRs.
- **Child PR** or **PR-on-PR** — informal terms for a PR whose base is the head branch of another PR.
- **Fan-out** — multiple PRs target the same PR branch. This is useful, but it is not one linear GitHub stack.

Do not call every graph of branch-relative PRs a GitHub stack. GitHub's first-class stack model is linear.

---

# Common usage scenarios

## 1. Split a large feature into reviewable layers

Instead of one PR containing schema changes, backend code, API changes, and UI work:

```text
main
  ← auth-schema
      ← auth-service
          ← auth-api
              ← auth-ui
```

Each layer has a focused diff and can be reviewed in its own context.

Use this when later work genuinely depends on earlier work and waiting for every lower-level PR to merge would unnecessarily serialize development.

## 2. Start dependent work before an earlier PR merges

Suppose PR #200 adds a reusable parser and PR #201 needs that parser.

Rather than duplicating the parser, waiting for #200, or temporarily mixing both features into one PR:

```text
main ← parser ← importer
       #200     #201
```

PR #201 can be developed and reviewed immediately while #200 is still under review.

## 3. Separate mechanical refactoring from semantic changes

A difficult change can become easier to review if a mechanical transformation lands below the behavioral change:

```text
main
  ← rename-and-move-only
      ← change-behavior
```

The first PR should make no semantic changes. The second PR becomes much smaller and more meaningful.

This is particularly effective for:

- file moves,
- symbol renames,
- generated-code updates,
- formatting migrations,
- API reshaping followed by behavior changes.

## 4. Demonstrate an architectural direction incrementally

A design can be expressed as several independently understandable steps:

```text
main
  ← introduce-interface
      ← migrate-first-consumer
          ← migrate-remaining-consumers
              ← remove-old-path
```

Reviewers can object to a lower architectural premise without having to reason about the entire final implementation at once.

## 5. Keep speculative upper layers moving

Sometimes the lower layer is likely to merge but details are still changing. Upper layers can remain draft PRs until the foundation stabilizes.

This is useful when the team wants visibility into the eventual direction without treating every upper layer as merge-ready.

---

# Special focus: a "PR on the PR"

## The problem

An author opens:

```text
main ← alice/feature
       PR #300
```

A reviewer thinks the PR would be cleaner with a nontrivial rewrite. A GitHub review comment is too small to express it well, and directly pushing to Alice's branch would blur authorship and remove the ability to compare alternatives cleanly.

The reviewer can branch from the PR's head and open another PR **against that branch**:

```text
main ← feature ← bob/cleanup
       #300      #301
```

PR #301 is, operationally, a PR proposing a change to PR #300.

If #301 is merged into `feature`, PR #300 immediately incorporates those commits because its head branch changed.

If #301 is closed, PR #300 is unaffected.

That makes the child PR a useful unit for:

- concrete code-review proposals,
- substantial cleanup,
- alternative refactors,
- adding tests to somebody else's PR,
- fixing edge cases without taking over the author's branch,
- demonstrating an architectural suggestion with executable code.

## Same-repository example

Assume the original PR is:

```text
base: main
head: feature
```

Create an alternative cleanup from the original PR's head:

```bash
git fetch origin
git switch -c cleanup-a origin/feature

# edit, test, commit
git add -A
git commit -m "Simplify parser state handling"
git push -u origin cleanup-a

gh pr create \
  --base feature \
  --head cleanup-a \
  --title "Alternative cleanup for parser state handling"
```

The key option is:

```text
--base feature
```

not `--base main`.

If the PR targeted `main`, its diff would include both the original feature and the cleanup, which defeats the purpose.

## What the child PR's diff means

Given:

```text
main:       A---B
                 \
feature:          C---D
                       \
cleanup-a:              E---F
```

The original PR shows approximately:

```text
C + D
```

The cleanup PR shows approximately:

```text
E + F
```

That isolation is the main reason to use this pattern.

The cleanup PR is not a replacement for the original PR. It is a proposal to modify the original PR's branch.

---

# Competing takes on the same PR

This is the most interesting extension of the PR-on-PR pattern.

Suppose Bob and Carol have different ideas for cleaning up Alice's PR:

```text
                  ← bob/cleanup-a    PR #301
                 /
main ← feature
       PR #300    \
                  ← carol/cleanup-b  PR #302
```

Or written as branch relationships:

```text
main ← feature ← cleanup-a
             ↖︎  cleanup-b
```

Both #301 and #302 use `feature` as their base.

This gives the original author and reviewers two independently testable, commentable alternatives.

## Why this is useful

A code-review conversation can otherwise degrade into prose such as:

> What if this were represented as a state machine instead?

followed by several rounds of ambiguity about what that would actually entail.

With sibling PRs, the conversation can instead compare concrete implementations:

```text
PR #301 — preserve current structure, simplify state transitions
PR #302 — replace state flags with an explicit state-machine type
```

Each proposal gets:

- its own diff,
- its own commits,
- its own CI run,
- line comments,
- review discussion,
- the ability to evolve independently,
- a clean close-without-merge outcome.

## This is not one official GitHub stack

Do **not** try to force this graph into GitHub's first-class stacked-PR model.

GitHub stacks are ordered chains:

```text
main ← A ← B ← C
```

Competing alternatives are a branch graph:

```text
main ← A ← B
         ↖︎ C
```

The alternatives use the same underlying idea — a PR can target another PR's branch — but they are ordinary sibling PRs rather than successive layers of one stack.

This distinction matters because GitHub's official stacked-PR feature has special stack-wide behavior for merge requirements, rebasing, CI metadata, and atomic merging. Do not assume those semantics apply to an arbitrary fan-out of ordinary PRs.

## Recommended convention for competing proposals

Make the relationship explicit in titles and descriptions.

Example titles:

```text
PR #300  Add incremental parser
PR #301  Alternative for #300: simplify parser state handling
PR #302  Alternative for #300: explicit state-machine design
```

In each alternative PR description, state:

```markdown
This PR targets the head branch of #300, not `main`.

It is one possible revision of #300 and is intended to be compared with #302.
Merging this PR updates #300; closing it leaves #300 unchanged.
```

Draft PRs are often appropriate while alternatives are exploratory.

## Choosing an alternative

When one proposal wins:

1. Merge the chosen child PR into the original PR branch.
2. Re-run or verify CI on the now-updated original PR.
3. Close the rejected sibling alternatives as superseded/not selected.
4. Continue reviewing the original PR against `main`.

Do not merge multiple competing alternatives merely because each passes CI. They may be mutually exclusive even when Git can merge them mechanically.

## A useful variation: experimental alternative

A reviewer can open a child PR solely to test an idea and explicitly mark it as non-mergeable:

```text
Draft: Experiment for #300 — replace polling with event dispatch
```

The value can be the diff and discussion itself. Closing the PR after the design question is settled is a successful outcome.

---

# PR-on-PR versus GitHub Suggested Changes

Use **Suggested Changes** for small, local edits that fit naturally into review comments.

Prefer a child PR when the proposal:

- changes several files,
- needs its own commits,
- needs CI,
- includes tests,
- changes architecture,
- needs discussion separate from the parent PR,
- has more than one viable implementation,
- would be awkward or intrusive to push directly to the author's branch.

A useful rule of thumb:

```text
one localized edit       → Suggested Change
coherent implementation  → child PR
multiple dependent units → linear stack
competing implementations→ sibling child PRs
```

---

# PR-on-PR versus pushing directly to the author's branch

Direct pushes are sometimes appropriate when the author explicitly wants collaborative editing and permissions allow it.

A child PR is preferable when you want to preserve a boundary between:

```text
the author's proposal
```

and:

```text
the reviewer's proposed modification of that proposal
```

Benefits of the child PR include:

- authorship remains clear,
- no unsolicited mutation of the author's branch,
- the proposal can be rejected by simply closing it,
- alternatives can coexist,
- discussion stays attached to the proposed modification,
- CI can validate the modification before it touches the parent branch.

---

# Creating an official linear GitHub stack

As of August 2026, GitHub provides first-class stacked pull requests in public preview.

## With GitHub CLI

GitHub documents the `github/gh-stack` extension.

Install it:

```bash
gh extension install github/gh-stack
```

Create the first layer:

```bash
gh stack init data-model
# edit
git add -A
git commit -m "Add data model"
```

Add another layer:

```bash
gh stack add service-layer
# edit
git add -A
git commit -m "Add service layer"
```

Add another:

```bash
gh stack add api-layer
# edit
git add -A
git commit -m "Expose service through API"
```

Submit the stack:

```bash
gh stack submit
```

Conceptually this produces:

```text
main ← data-model ← service-layer ← api-layer
```

with one PR for each branch relationship.

Other useful stack operations include cascading rebase/push and stack-aware merging. Consult the current GitHub documentation before relying on exact preview CLI behavior in automation.

## From the GitHub website

The underlying mechanism does not require the CLI.

For a linear sequence:

1. Create the bottom PR against `main` or another trunk.
2. Create the next PR with the first PR's head branch as its base.
3. Choose GitHub's **Create stack** option when offered.
4. Repeat upward.

GitHub can also recognize some existing linear PR relationships and offer to link them as a stack.

---

# How official GitHub stacks behave

When reasoning about GitHub's first-class stack feature, account for the following current behavior.

## Same repository only

Official stacked PRs require all branches in the stack to be in the same repository.

Cross-fork stacks are not supported by the first-class stack feature.

This is distinct from ordinary GitHub pull requests, which can use forks.

## Stack-wide requirements

GitHub evaluates required reviews, required status checks, and CODEOWNERS requirements for stack layers against the stack's trunk/base rules rather than treating a middle branch as an isolated protected destination.

A higher layer cannot simply bypass requirements that apply below it.

## Linear history is required

Official stacks require a fully linear history between stack branches when merging.

Changes to a lower layer or movement of the trunk may require a cascading rebase of the upper layers.

GitHub's stack tooling exists partly to manage this bookkeeping.

## Merge behavior is stack-aware

GitHub can merge contiguous layers of an official stack together in order. The current stack feature supports merge-commit, squash, and rebase merge methods with stack-specific semantics.

Do not extrapolate this behavior to unrelated ordinary PRs that merely happen to target feature branches.

## Current preview limitations

As of August 2026, GitHub documentation notes that:

- stacked PRs are in public preview and behavior may change,
- branches must be in the same repository,
- GitHub Desktop does not support stacked PRs,
- auto-merge is not supported for stacked PRs.

When exact behavior matters, verify the current GitHub documentation rather than relying on this skill's snapshot.

---

# Fork considerations

Forks require extra care.

An ordinary PR can be opened from a fork, and GitHub exposes base/head repository and branch choices for cross-fork pull requests. However, GitHub's first-class stacked-PR feature explicitly does **not** support cross-fork stacks.

If the original PR's head branch lives in a contributor's fork, do not blindly apply the same-repository recipe:

```bash
gh pr create --base ORIGINAL_HEAD_BRANCH
```

The branch may not exist in the repository where you are attempting to create the child PR, and permissions or fork topology may prevent the desired relationship.

Instead:

1. Identify the repository that owns the original PR's head branch.
2. Determine whether GitHub permits the proposed head repository/branch to target that repository and branch.
3. Check whether collaboration permissions allow the intended workflow.
4. If the graph becomes awkward, prefer a same-repository temporary branch when maintainers can create one.
5. For a very small change, consider Suggested Changes instead.

Do not describe a cross-fork construction as an official GitHub stack.

Also distinguish a child PR from GitHub's **Allow edits from maintainers** feature. Allowing edits lets maintainers push to a fork PR's branch; a child PR preserves the proposed modification as a separate reviewable object.

---

# CI and testing strategy

## For a normal child PR

A child PR targeting `feature` tests the combined state:

```text
feature + child changes
```

That is normally what you want: the question being asked is whether the proposed revision works on top of the original PR.

After the child merges into `feature`, the parent PR has changed. Verify that the parent PR's checks run again or otherwise validate the final state intended for `main`.

## For competing alternatives

Run CI separately on each sibling:

```text
feature + cleanup-a
feature + cleanup-b
```

Do not use a passing result for one alternative as evidence for another.

## For official stacks

GitHub's stack feature has stack-aware rules and metadata. Avoid writing custom CI logic that assumes the immediate base branch of a middle PR is the ultimate target branch.

If CI cost becomes substantial, consult GitHub's current guidance for optimizing CI for stacked pull requests.

---

# Review strategy

## Review bottom-up when dependencies matter

For a true stack:

```text
main ← A ← B ← C
```

review `A` first when understanding `B` requires accepting `A`'s design.

Upper-layer review is still useful before lower layers are approved, but reviewers should distinguish:

- objections to the current layer,
- objections inherited from a lower layer.

Avoid repeatedly commenting on the same lower-layer issue in every upper PR.

## Review child PRs as changes to the proposal, not to trunk

For:

```text
main ← feature ← cleanup
```

the question in the cleanup PR is:

> Is `feature + cleanup` better than `feature`?

not:

> Is the entire combined feature ready for `main`?

The latter remains the parent PR's question.

## Compare sibling alternatives against the same base

For:

```text
feature ← cleanup-a
        ↖︎ cleanup-b
```

keep both alternatives based on approximately the same parent state when possible. Otherwise comparisons become contaminated by unrelated drift.

If the parent changes materially during the experiment, rebase or reconstruct the alternatives as appropriate before drawing conclusions.

---

# Merge-order rules

## Linear stack

For:

```text
main ← A ← B ← C
```

the conceptual dependency order is:

```text
A, then B, then C
```

GitHub's official stack tooling can merge contiguous portions in stack-aware ways; use that rather than manually improvising when working with a linked official stack.

## Parent plus child PR

For:

```text
main ← feature ← cleanup
```

if the cleanup is intended to become part of the original PR:

```text
cleanup → feature
feature → main
```

Do not merge `feature` into `main` first and then expect the child PR to remain a PR *on that PR*; its conceptual base has disappeared.

## Competing siblings

For:

```text
feature ← cleanup-a
        ↖︎ cleanup-b
```

choose first, merge second.

Normally exactly one alternative is merged unless the alternatives were intentionally designed to compose.

---

# Failure modes and cautions

## Accidentally targeting `main`

The most common conceptual error in a PR-on-PR workflow is opening:

```text
cleanup → main
```

instead of:

```text
cleanup → feature
```

The resulting diff contains the parent PR and the cleanup together.

Fix the base branch or recreate the PR as appropriate.

GitHub permits changing the base branch of an open PR, but warns that doing so can remove commits from the timeline and make review comments outdated. Treat a late base change with care.

## Lower-layer changes alter upper-layer context

If `A` changes under `B`, the meaning and mergeability of `B` may change.

For an official stack, use stack-aware rebasing.

For ordinary child/sibling PRs, rebase deliberately and expect conflict resolution or changed diffs.

## Force-push review churn

Rebasing stacked branches can rewrite commits and invalidate review context. Prefer small, comprehensible updates and explain substantial rebases to reviewers.

## Deleting intermediate branches too early

A branch can be both:

- the head of one PR, and
- the base of another.

Do not delete it casually while dependent PRs still need it.

## Treating alternatives as sequential layers

If `cleanup-a` and `cleanup-b` are competing answers to the same question, this is wrong:

```text
feature ← cleanup-a ← cleanup-b
```

That graph says B depends on A.

Use siblings instead:

```text
feature ← cleanup-a
        ↖︎ cleanup-b
```

## Confusing "can merge" with "should compose"

Git may be able to merge two experimental alternatives without conflicts. That does not mean their designs are compatible.

## Hiding inherited changes in the wrong PR

A layer should contain the smallest coherent delta relative to its direct base. If a change logically belongs in a lower layer, put it there and cascade/rebase upward rather than smuggling it into an upper PR.

---

# When not to use stacked or child PRs

Avoid adding branch structure merely for novelty.

Prefer ordinary independent PRs when the changes do not depend on one another:

```text
        ← feature-x
main
        ← feature-y
```

Prefer Suggested Changes or normal review comments when the proposed correction is tiny.

Prefer direct collaboration on the same branch when all authors explicitly want shared ownership and a separate review boundary would add no value.

Prefer one PR when splitting would make every layer meaningless on its own and reviewers would have to reconstruct the entire stack mentally anyway.

---

# Decision guide

| Situation | Recommended pattern |
|---|---|
| One small line-level correction | Suggested Change |
| Reviewer has a coherent multi-file fix for an open PR | Child PR targeting the PR head branch |
| Two reviewers have different implementations for fixing the same PR | Sibling child PRs targeting the same PR head branch |
| Feature naturally divides into dependent layers | Official linear stacked PRs |
| Two changes are unrelated | Independent PRs to trunk |
| Reviewer is invited to co-author directly and no alternative needs preservation | Push to shared PR branch |
| Original PR comes from a fork | Evaluate fork/base permissions; do not assume official stacking works |

---

# Guidance for an assistant

When helping with stacked PRs:

1. First identify the actual branch graph.
2. Name the head and base branch of every PR under discussion.
3. Distinguish a **linear official stack** from ordinary PRs that happen to target PR branches.
4. For a user's "PR on the PR" request, prefer a child PR whose base is the original PR's head branch.
5. If multiple alternatives are proposed, model them as siblings, not successive stack layers.
6. Explain what merging each PR changes.
7. Warn when a fork prevents use of GitHub's first-class stack feature.
8. Do not assume GitHub preview behavior is permanent; verify current documentation when exact CLI/UI/merge semantics matter.
9. Prefer diagrams showing branch relationships whenever the graph is nontrivial.
10. When giving commands, make the base branch explicit so the user can see which diff GitHub will review.

A concise diagnostic format is:

```text
Parent PR:       feature → main
Proposed PR:     cleanup → feature
Effect of merge: cleanup commits become part of `feature`, so the parent PR updates
```

For alternatives:

```text
Parent PR:       feature → main
Alternative A:   cleanup-a → feature
Alternative B:   cleanup-b → feature
Relationship:    siblings / competing proposals, not one linear stack
```

---

# References

GitHub's stacked-PR feature is evolving. Prefer current GitHub documentation for product-specific details:

- Stacked pull requests reference: https://docs.github.com/en/pull-requests/reference/stacked-pull-requests
- Creating stacked pull requests: https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests
- Managing stacked pull requests: https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/managing-stacked-pull-requests
- Merging stacked pull requests: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests
- Changing a PR's base branch: https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/changing-the-base-branch-of-a-pull-request
- Creating a PR from a fork: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork
- Allowing changes to a fork PR branch: https://docs.github.com/en/pull-requests/how-tos/work-with-forks/allowing-changes-to-a-pull-request-branch-created-from-a-fork
- Giving reviews / Suggested Changes: https://docs.github.com/en/pull-requests/concepts/giving-reviews
