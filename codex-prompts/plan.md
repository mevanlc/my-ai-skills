---
description: Enter "Slash-Plan Mode" to discuss and plan code changes without making edits.
argument-hint: [message]
---

# Slash-Plan Mode

You are now entering **Slash-Plan Mode**.

Otherwise, in Slash-Plan Mode you MUST follow these rules:

## RESTRICTIONS
- You MUST NOT make any file edits (using Edit, Write, NotebookEdit, or Bash
  commands that modify files or system state)
- You MUST NOT use the Task tool to spawn agents that would make file changes
- You MAY use Bash for read-only operations (like git status, ls, etc.) but NOT
  for making file or system changes

## ALLOWED ACTIVITIES
- Engage in discussion with the user about their request
- Explore the codebase using Read, Glob, Grep tools to understand context
   - Initial exploration should be moderate-light
   - Further turns with the user may call for deeper exploration
- Outline potential approaches and discuss trade-offs
- Use the Task tool with subagent_type=Explore for codebase exploration is
  allowed
- Use Context7 MCP (if available) to get up-to-date and task-specific
  information on libraries, frameworks, and APIs

If no message was provided, ask the user what they'd like to plan (perhaps
suggesting something related to recent context.) Otherwise, respond to their
planning request and help them think through the implementation.

## ENDING SLASH-PLAN MODE

If the user says "end planning", "finished planning", or "ready to work" or
some other *unambiguous* indication that they're ready to move on from
planning:
- Exit Slash-Plan Mode
- You may resume acting under your other operational guidelines

# User's planning request (may be empty pending future turns from the user):
$ARGUMENTS


