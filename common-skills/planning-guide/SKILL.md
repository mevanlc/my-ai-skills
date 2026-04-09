---
name: planning-guide
description: Help decide which planning mode to use for the current task. Compares built-in /plan vs /ultraplan and recommends one based on the situation.
argument-hint: "<optional: brief description of the task>"
---

# Planning Guide

The user wants help choosing a planning approach. Based on their task (from `$ARGUMENTS` or recent conversation context), recommend one of the options below. Be concise — a few sentences, not an essay.

## Options

### `/plan` (built-in)

Best when:
- The task is well-scoped and you already understand the problem space
- You need a quick implementation roadmap (seconds to a few minutes)
- The work is within a codebase you're already in
- No external research needed — the answers are in the code, docs, or your head
- The plan will be executed in the same session

Examples: refactoring a module, adding a feature to existing code, fixing a bug with a known cause, reorganizing project structure.

Output: lives in conversation context only (no file artifact).

### `/ultraplan` (custom)

Best when:
- Starting something new or entering unfamiliar territory
- The task needs research before you can plan (libraries, data formats, APIs, prior art)
- You want to explore multiple approaches before committing
- The plan will be handed off to a different session/agent for implementation
- There are unknowns you need to investigate before you can even scope the work
- The task is large enough to benefit from MVP phasing

Examples: building a new tool from scratch, reimplementing something in a different language, integrating with an unfamiliar API, any project where "I'd need to check how X works" comes up more than once.

Output: writes an `ULTRAPLAN.md` file (durable artifact that survives the session). Includes research findings, testing strategy, and handoff material.

### No formal plan needed

Best when:
- The task is a single, clear action (< 3 steps)
- You already know exactly what to do
- Overhead of planning exceeds the work itself

Examples: renaming a variable, adding a dependency, writing a single test, fixing a typo.

## Instructions

1. **Read the room from the CWD.** Before recommending, quickly assess the workspace:
   - If it's an established repo (has src/, multiple commits, existing code): leans toward `/plan` — the context is already here.
   - If it's empty or nearly empty (fresh `cargo init`, just a README, no real code yet): leans toward `/ultraplan` — there's likely research and scaffolding decisions ahead.
   - If ambiguous, ask briefly: "Is this an existing project you're extending, or something new?"
2. If `$ARGUMENTS` is provided, factor that together with the CWD signal and recommend the best option with a brief rationale.
3. If no arguments, ask what the user is working on, then recommend.
4. After recommending, offer to launch it (e.g., "Want me to start `/ultraplan <topic>`?" or "Want me to enter `/plan`?").
5. If the user seems uncertain, suggest starting with `/plan` — they can always upgrade to `/ultraplan` if they hit unknowns during planning.
