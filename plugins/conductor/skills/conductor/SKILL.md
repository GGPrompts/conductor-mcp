---
name: conductor
description: >
  Orchestrate AI workers with tmux using the cm CLI and conductor MCP primitives.
  Use when the user asks to spawn workers,
  manage tmux panes/sessions, coordinate parallel tasks, run multiple AI agents,
  monitor worker progress, or use text-to-speech announcements. Also use when you see
  conductor MCP primitives available (spawn_worker, smart_spawn, smart_spawn_wave,
  wait_for_signal, send_signal).
---

# Conductor — Orchestration Guide

Prefer `cm` via Bash for worker communication, monitoring, and tmux management.
Use MCP for the five canonical spawn/signal primitives: `spawn_worker`,
`smart_spawn`, `smart_spawn_wave`, `wait_for_signal`, and `send_signal`. Other MCP
tools are compatibility shims; use their CLI equivalents in the reference.
Every `cm` verb supports `--json` for structured output.

## Quick Start

The most common workflow is spawning workers for parallel tasks:

```python
# MCP primitives
# Spawn a single worker in a visible pane
smart_spawn(issue_id="task-name", project_dir="/path/to/project")

# Spawn multiple workers at once
smart_spawn_wave(issue_ids="task-1,task-2,task-3", project_dir="/path/to/project")

# Use a different AI agent
smart_spawn(issue_id="review", project_dir="/path", profile="codex")
```

## Worker Communication: cm send

Use `cm send` to communicate with workers. It handles the delay before Enter
automatically and submits by default; use `--no-submit` to type without Enter.

```bash
cm send task-name "your prompt here"
cm send task-name "partial text" --no-submit
```

## Monitoring

```bash
cm list workers                    # See all active sessions
cm context task-name               # Check context usage
cm worker capacity --threshold 60  # Find workers below 60% context
cm capture task-name --lines 50     # See recent terminal output
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

For CLI mappings, MCP primitive signatures, workflows, and hotkeys, see:

- `references/tool-reference.md` — canonical CLI commands and MCP primitives with parameters
- `references/workflows.md` — common multi-step patterns
- `references/hotkeys.md` — tmux keybinding cheat sheet
