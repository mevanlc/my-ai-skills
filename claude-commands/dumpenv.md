---
allowed-tools: Bash(*), Edit, Glob, Grep, NotebookEdit, NotebookRead, Read, SlashCommand, Task, TodoWrite, WebFetch, WebSearch, Write, AskUserQuestion
description: slash command to help debug slash commands -- no response necessary from the model
argument-hint: [args]
model: haiku
---

# /dumpenv is a test command the user uses to debug slash commands. No response is necessary from the model unless an error occurs.

!`env | sort > /tmp/slashcommand_env.bash`
!`echo '== $ARGUMENTS ==' > /tmp/slashcommand_args.bash`
