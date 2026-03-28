---
name: plan-mode
description: Planning-only collaboration for code, tooling, and workflow changes. Use when the user wants to discuss approaches, explore the codebase, compare tradeoffs, or produce an implementation plan without making file edits, running installs, or taking other state-changing actions.
---

# Plan Mode

Use this skill to stay in discussion and planning mode. Base the plan on the user's latest request and the surrounding conversation; skills do not receive a separate `$ARGUMENTS` string.

## Restrictions

- Do not make file edits.
- Do not run commands that modify files, Git history, packages, databases, or other system state.
- Do not spawn workers that would make changes.
- Keep exploration moderate and targeted unless the user asks for a deeper planning pass.

## Allowed Work

- Discuss requirements, scope, risks, and tradeoffs.
- Explore the codebase with read-only commands and file inspection.
- Produce outlines, task breakdowns, migration strategies, and testing plans.
- Use external documentation or research tools when up-to-date information materially improves the plan.

## Workflow

1. Identify the planning target from the latest user request.
2. Gather enough context to understand constraints, existing patterns, and unknowns.
3. Present one or more viable approaches with tradeoffs.
4. Recommend a concrete plan with ordered implementation steps and validation points.
5. Stop after planning. Do not implement unless the user explicitly says to move on from planning.

## Exit Condition

- If the user clearly says they are ready to implement, stop applying this skill and resume the normal execution workflow.
- If no planning target was provided, ask what they want to plan.
