---
name: explain-uncommitted
description: Explain the content, purpose, and likely intent of uncommitted Git changes. Use when the user wants to understand what changed locally and why.
---

# Explain Uncommitted Changes

Help the user understand what the uncommitted changes do, how they fit together, and what they appear intended to accomplish. Keep the explanation grounded in the repo and adapt it to the changes and the user's request.

## Invocation

| Input | Guidance |
|---|---|
| `$explain-uncommitted` | Choose the depth and structure that best explain the changes. |
| `$explain-uncommitted detail` or `$explain-uncommitted detailed` | Give a detailed walkthrough of the logical changes, their effects, and relevant implementation details. |
| `$explain-uncommitted brief` | Give a short overview of the main changes and their purpose. |
| `$explain-uncommitted <freeform comment>` | Use adaptive depth and interpret the comment as additional guidance about focus, scope, audience, or presentation. |

Depth keywords can be combined with freeform guidance, such as `$explain-uncommitted brief focus on user-visible behavior`. Interpret the request naturally rather than requiring rigid argument syntax. Depth controls the explanation, not whether relevant changes are inspected.

## Approach

- Use the current repo unless the user identifies another. Cover staged changes, unstaged changes, and non-ignored untracked files by default; honor any narrower scope the user requests. Inspect both staged and unstaged diffs, since a combined diff can hide changes that cancel each other out. Read untracked files as needed; ordinary Git diffs omit them.
- Read surrounding code, documentation, tests, or relevant history when they help establish context. Explain meaningful changes in behavior or content, connecting related edits across files and separating unrelated work when appropriate.
- Lead with the overall purpose when the evidence supports one, then explain the concrete changes that establish it. Distinguish what the changes demonstrably do from inferred motivation; acknowledge uncertainty instead of inventing intent.
- Choose a useful narrative, grouping, and level of detail. Include file references or before/after examples where they help understanding. There is no required report template or exhaustive file inventory, and a review checklist is not part of the default task.
- Keep this task read-only: do not edit, stage, discard, or commit changes. If there are no uncommitted changes in scope, say so. If relevant content cannot be inspected or its effects remain unclear, state that limitation.
