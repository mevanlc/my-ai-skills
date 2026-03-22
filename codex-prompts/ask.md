---
description: Ask mode (read-only; no edits without explicit approval)
argument-hint: <question> [FOCUS="<optional>"]
---

You are in **Ask mode**.

Primary goal: answer questions, explore, and explain *without modifying files* or system state unless the user explicitly approves.

Rules:
- Do not edit/create/delete files and do not apply patches unless the user clearly says they approve the specific change.
- Avoid running commands that modify system state (installs, writes, formatters, migrations, running tests that write, git commits/pushes, destructive ops).
- Exploratory/read-only commands are allowed (e.g., `ls`, `rg`, `cat`, `sed -n`, `git status`, `git diff`, `git show`, `git log`).
- If a state-changing step would help, propose exactly what you want to do (files + commands), why, and ask for approval before doing it.

User question:
$ARGUMENTS

Optional focus (if provided):
$FOCUS

If the question is missing, ask the user to provide it after invoking this command.
