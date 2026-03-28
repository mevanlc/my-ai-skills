---
name: ask-mode
description: Read-only investigation and explanation for codebase, tooling, or environment questions. Use when the user wants analysis, debugging help, architectural discussion, or general answers without file edits, installs, commits, or other state-changing actions unless they later approve a specific write operation.
---

# Ask Mode

Use this skill to answer and investigate without changing the workspace or system state. Treat the user's latest request and surrounding conversation as the input; do not look for a separate slash-command argument placeholder.

## Operating Rules

- Stay read-only unless the user clearly approves a specific write action.
- Do not edit, create, delete, rename, or format files.
- Do not run installs, migrations, commits, pushes, rebases, or other state-changing commands.
- Treat tests as disallowed if they write files, mutate caches, or otherwise change state.
- Use exploratory commands freely when they are read-only, such as `ls`, `rg`, `git status`, `git diff`, `git show`, and file reads.

## Workflow

1. Identify the actual question from the user's latest message and current context.
2. Explore only as much as needed with read-only tools.
3. Answer directly and cite relevant files, commands, or observations.
4. If a state-changing step would materially help, propose the exact files and commands first and ask for approval before doing it.

## Escalation

- If the user has not actually asked a question yet, ask what they want to investigate.
- If the request is ambiguous, clarify the goal rather than guessing a write action.
- If the user later approves a concrete change, stop applying this skill and proceed under the normal editing workflow.
