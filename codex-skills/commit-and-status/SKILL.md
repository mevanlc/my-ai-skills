---
name: commit-and-status
description: Create a conventional Git commit from the current worktree and summarize the resulting repository status. Use when the user asks to commit current changes, especially when they want the commit message derived from the work or want a quick post-commit `git status` report.
---

# Commit And Status

Use this skill when the user wants the current changes committed and wants the commit described with a conventional commit message. Treat the user's latest request, the current Git state, and the actual diff as the inputs; skills do not receive a separate slash-command argument placeholder.

## Workflow

1. Inspect the current repository state with `git status` and relevant diffs.
2. Determine the intended commit scope from the user request and current context.
3. Derive a concise conventional commit message from the actual changes unless the user already specified one.
4. Stage the intended changes and create the commit.
5. Run `git status` after the commit and summarize the result for the user.

## Commit Rules

- Prefer a conventional commit subject such as `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, or `chore: ...`.
- Base the message on what changed, not on the wording of an old slash-command argument.
- Do not mention AI tools in the commit message.
- If there is nothing to commit, say so instead of forcing an empty commit.
- If the worktree contains unrelated changes and the intended scope is ambiguous, clarify before committing.

## Reporting

- Tell the user the commit message you used.
- Relay the important lines from post-commit `git status`, especially whether the tree is clean or which files remain modified or untracked.
