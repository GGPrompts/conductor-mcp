---
name: conductor
description: >
  Orchestrate Claude Code workers with tmux. Use when the user asks to spawn workers,
  manage tmux panes/sessions, coordinate parallel tasks, run multiple AI agents,
  monitor worker progress, or use text-to-speech announcements. Also use when you see
  conductor MCP tools available (spawn_worker, smart_spawn, send_keys, etc.).
---

# Conductor MCP — Orchestration Guide

You have access to the conductor MCP server for orchestrating Claude Code workers via tmux.

## Quick Start

The most common workflow is spawning workers for parallel tasks:

```python
# Spawn a single worker in a visible pane
smart_spawn(issue_id="task-name", project_dir="/path/to/project")

# Spawn multiple workers at once
smart_spawn_wave(issue_ids="task-1,task-2,task-3", project_dir="/path/to/project")

# Use a different AI agent
smart_spawn(issue_id="review", project_dir="/path", profile="codex")
```

## Critical Pattern: send_keys

Always use `send_keys` to communicate with workers. It handles timing automatically:

```python
send_keys(session="task-name", keys="your prompt here")  # submit=True by default
send_keys(session="task-name", keys="partial text", submit=False)  # type without Enter
```

## Monitoring

```python
list_workers()                          # See all active sessions
get_context_percent("task-name")        # Check context usage
get_workers_with_capacity(60)           # Find workers below 60% context
capture_worker_output("task-name")      # See recent terminal output
```

## Profiles

Use `profile="name"` with smart_spawn to launch different tools:

| Profile | Tool |
|---------|------|
| `claude` | Claude Code (default) |
| `codex` | OpenAI Codex CLI |
| `gemini` | Google Gemini CLI |
| `copilot` | GitHub Copilot CLI |
| `tfe` | Terminal file explorer |
| `lazygit` | Terminal git UI |

## Reference

For detailed tool signatures, workflows, and hotkeys, see:
- `references/tool-reference.md` — all 41 tools with parameters
- `references/workflows.md` — common multi-step patterns
- `references/hotkeys.md` — tmux keybinding cheat sheet
