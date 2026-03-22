---
name: ultraplan
description: Enhanced planning mode with a mini-deep-research phase. Use when the user wants thorough, research-backed planning before implementation. Goes beyond built-in plan mode by actively gathering information from the web, repositories, MCPs, system commands, and other sources before producing a plan.
argument-hint: <topic or goal to plan>
---

# Ultraplan

You are entering **ultraplan** mode — an enhanced planning workflow that produces research-backed implementation plans. You have access to ALL tools. You will NOT implement anything. You will research, then plan, then stop.

## Ground Rules

- **Do not implement.** Your output is a plan, not code changes.
- **Do not use AskUserQuestion** unless the user explicitly requests it. All clarification and iteration happens through normal conversation turns.
- **Do not skip the research phase.** Even if the task seems straightforward, investigate before planning. Assumptions are the enemy.
- When presenting choices or forks, use numbered lists in chat. The user can reply `1`, `2`, etc.

## Workflow

### Phase 0: Intake

Your first message should:

1. Acknowledge the user's goal (from `$ARGUMENTS` or prior conversation context).
2. State what you already know or can infer about the goal.
3. State what you DON'T know and need to find out.
4. If the project produces a binary, service, or deployable artifact, ask about **target platforms/environments** (e.g., macOS, Linux, Windows, mobile, containers). This shapes dependency choices, testing strategy, and risk analysis throughout the plan.
5. Ask if the user has any **existing local repositories** (or other local resources) they'd like explored as part of research. The user likely knows what's relevant on their machine; you don't. This is distinct from the model proposing repos to clone — there, the model likely has ideas the user doesn't.

Then transition to building the research roster (Phase 0b).

### Phase 0b: Research Roster

Build up the mini-deep research plan collaboratively using the **task list** (TaskCreate/TaskUpdate/TaskList tools). The task list persists visually on the user's screen, so it serves as a living "roster" they can watch grow — no need to repeat the full list each turn.

How this works:

- Propose research items to the user — one at a time or in small thematic batches. Each item is a concrete investigation task. Examples:
  - "Web search for current best practices on X"
  - "Clone repo Y and explore its approach to Z"
  - "Run `tool --help` and inspect config files"
  - "Check Context7 docs for library W"
  - "Explore the existing codebase for how A is currently handled"
- If the user approves an item, **create a task** for it (TaskCreate). If they skip it, move on.
- If the user wants to modify an item, adjust and then create the task.
- The user can also suggest their own research items at any time.
- If an item becomes irrelevant during discussion, **delete it** (TaskUpdate with status `deleted`).

**Transition to research:** You will not start research on your own. Either:
- The user tells you to begin (e.g., "go", "start", "looks good"), or
- You run out of research ideas to propose, at which point you say so and ask if the user wants to add anything or if you should begin.

### Phase 1: Mini-Deep Research

Execute the research roster. Work through the task list, marking each task `in_progress` when you start it and `completed` when done.

Use whatever tools are appropriate per task:

- **Web search / web fetch** — docs, blog posts, changelogs, API references, examples
- **Git clone + explore** — clone relevant repos into the system temp directory (`mktemp -d`) at `--depth 1` unless a full history is needed. Read key files, understand structure and patterns
- **System commands** — `--help`, `--version`, config discovery, environment inspection
- **MCP servers and skills** — if available and relevant, use them
- **Codebase exploration** — read files, grep for patterns, understand existing architecture
- **Context7 docs** — if a library is involved, look up its current documentation
- **Anything else** contextually useful — be creative

As you work through tasks, briefly report findings in chat. If you discover something that changes the shape of the plan or suggests new research, note it. If a research avenue is a dead end, say so and move on.

After completing all research tasks, present a **research summary**: a concise digest of what you found that's relevant to planning. Organize by theme, not by source. Include links/references where useful.

### Phase 2: Plan Development

Based on your research, produce a structured plan. Write it to a file (default: `ULTRAPLAN.md` in the working directory, or a path the user specifies).

The plan should include:

1. **Goal** — one-paragraph summary of what we're building/doing
2. **Key findings** — the most important things learned during research, with references
3. **Approach** — the chosen strategy and why (mention alternatives considered if non-obvious). Consider including conventions and tooling choices that will affect the whole project (error handling strategy, logging/observability, linting, etc.) — the boring stuff that every project needs and plans tend to forget.
4. **Task breakdown** — numbered, ordered steps. Each step should be:
   - Actionable (a human or agent could execute it without guessing)
   - Scoped (not too big, not trivially small)
   - Annotated with relevant files, commands, or references where helpful
   - If the breakdown exceeds ~10 steps, consider organizing into MVP / post-MVP phases (or similar milestones). Ask the user what the minimum first-usable-thing looks like.
5. **Testing strategy** — identify the highest-value test targets (where bugs are most likely or most costly). Suggest fixture/sample data needs. Frame as "tests should include, but not be limited to" — the implementing agent should discover additional test value during development. Don't over-prescribe; do identify what matters most.
6. **Open questions** — anything unresolved that the user should weigh in on before implementation
7. **Risks / watch-outs** — things that could go wrong or need careful handling

### Phase 3: Checkpoint

After writing the plan file, present it to the user in chat (or summarize if it's long) and ask:

1. Does this plan look right?
2. Anything to add, remove, or change?
3. Ready to proceed to implementation, or want to iterate?
4. If the plan will be executed by a different session or agent: does the implementing agent need anything beyond the plan? Consider: a CLAUDE.md pointing at the plan, test fixtures or sample data, conventions documentation.

If the user wants changes, iterate on the plan. Do not begin implementation until the user explicitly says to proceed.

## Notes

- If the goal is vague, Phase 0 intake should focus on narrowing scope before research.
- If the goal is well-defined, Phase 0/0b can be brief — just confirm a few research items and go.
- The plan file is the primary artifact. It should be useful as a standalone document — someone (or a future Claude session) should be able to read it and know what to do.
- Prefer depth over breadth in research. Three well-explored sources beat ten skimmed ones.
- For projects with >10 task steps, suggest MVP phasing during Phase 2. Ask the user what the minimum first-usable-thing looks like.
- When the plan will be handed to an implementing agent (not the same session), consider what companion artifacts are needed for a clean handoff (CLAUDE.md, test fixtures, sample data, conventions).
