---
name: poll-gh-actions-run
description: Poll a specific GitHub Actions workflow run to completion with authenticated `gh api` access, stop promptly on newly completed job or step errors, and resume later while suppressing already reported errors via a continuation token. Use when the user asks to wait for, watch, monitor, or poll a GitHub Actions run, especially for private repositories, when mid-run failures should return control early, or when continuing a previously interrupted poll.
---

# Poll GitHub Actions Run

Use the bundled `scripts/poll-gh-actions-run` executable. Do not recreate its
polling or persistent-state logic in an ad hoc command loop.

## Prepare

1. Resolve `<skill-dir>` as the directory containing this `SKILL.md`.
2. Find and verify the authenticated CLI before polling:

   ```sh
   which gh
   gh auth status
   ```

3. Obtain exactly one run in either accepted form:

   ```text
   OWNER/REPO/RUN_ID
   https://github.com/OWNER/REPO/actions/runs/RUN_ID
   ```

The script queries run and paginated job/step data through authenticated
`gh api` calls. The active `gh` account must have access to the repository;
private repositories need no different invocation.

## Poll

Run the bundled executable directly:

```sh
poller="<skill-dir>/scripts/poll-gh-actions-run"
"$poller" OWNER/REPO/RUN_ID
```

Let it remain active until the run completes or it detects a new error. The
monitoring is read-only: do not dispatch, rerun, cancel, or otherwise mutate a
workflow unless the user separately requests that action.

The script keeps stdout machine-readable:

- If it stops before completion, stdout contains only a six-character token.
- If the run completes, stdout is empty.
- Diagnostics, detected errors, and the final conclusion go to stderr.

Preserve the token exactly. Do not mix stderr into stdout when capturing it:

```sh
token=$("$poller" OWNER/REPO/RUN_ID)
```

## Continue

Resume the same run with the emitted token:

```sh
"$poller" --continue "$token" OWNER/REPO/RUN_ID
```

The continued invocation ignores every job or step error already recorded for
that token. It remains active until the run finishes or a different error
appears; a new early stop emits the same token. Never invent a token or reuse
one with another run.

Saved state lives under
`${TMPDIR:-/tmp}/gh-actions-run-poll/OWNER/REPO/RUN_ID.XXXXXX`. Do not remove it
while the run is active. The script removes that run's state after completion.

## Interpret the Result

- Exit `0`: completed with `success`, `neutral`, or `skipped`.
- Exit `1` with a token: stopped at a newly observed mid-run error.
- Exit `1` without a token: completed with an unsuccessful conclusion.
- Exit `2`: usage, API, or state error. If polling had established resumable
  state, stdout still contains its token.
- Exit `130` or `143`: interrupted or terminated; established resumable state
  still produces its token.

Report the detected job or step, the run URL, whether the run is still active,
and the continuation token when one was emitted. Distinguish a local/API error
from a workflow-generated error.

Use `GH_RUN_POLL_INTERVAL` only when a non-default polling delay is requested.
Use `GH_RUN_POLL_STATE_DIR` only for isolated testing or an explicitly chosen
state location.
