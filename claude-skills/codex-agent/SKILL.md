---
name: codex-agent
description: Launch a Codex agent session to handle a task autonomously. Use when the user wants to delegate work to a Codex agent, run a Codex task, or continue an existing Codex session.
argument-hint: <prompt> OR --continue <session_id> <prompt>
---

# Codex Agent Launcher

Run tasks via `codex-agent`, a wrapper around `codex --yolo --profile agent exec`.

## Usage

Parse `$ARGUMENTS` to determine the mode:

### New session (default)

If no `--continue` / `-c` flag is present, treat the entire argument string as the prompt:

```bash
codex-agent -n "$ARGUMENTS"
```

### Continue session

If `$ARGUMENTS` starts with `--continue <session_id>` or `-c <session_id>`, extract the session ID and pass the rest as the prompt:

```bash
codex-agent -c <session_id> <remaining prompt>
```

## Behavior

- Run the command via Bash and return the output to the user.
- If the command fails, show the error and suggest corrections.
- If no arguments are provided, show the usage help (`codex-agent -h`).
