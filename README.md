# conductor-mcp

A lightweight MCP server for orchestrating Claude Code workers from any terminal.

**No Chrome required.** Brings TabzChrome's orchestration superpowers to iTerm, Kitty, Alacritty, Windows Terminal, or any terminal you prefer.

## Features

### Core Orchestration
| Tool | Description |
|------|-------------|
| `send_prompt` | Send text to Claude/Codex with proper delay for submission |
| `spawn_worker` | Create worktree + tmux session + inject beads context |
| `speak` | TTS announcements via edge-tts |
| `kill_worker` | Clean up worker session |
| `list_workers` | List active worker sessions |
| `get_worker_status` | Read Claude state from /tmp/claude-code-state |
| `capture_worker_output` | Get recent terminal output |

### Pane Management (Visual Grid)
| Tool | Description |
|------|-------------|
| `split_pane` | Split current pane horizontally or vertically |
| `create_grid` | Create grid layout (2x2, 3x1, 4x1, etc.) for multiple workers |
| `list_panes` | List all panes with their status |
| `focus_pane` | Switch focus to a specific pane |
| `kill_pane` | Kill a specific pane |
| `spawn_worker_in_pane` | Spawn a worker in an existing pane |

## The Key Differentiator

The tmux MCP's `execute-command` sends keys immediately, which causes Claude/Codex prompts to create a newline instead of submitting. `send_prompt` fixes this:

```python
# What tmux MCP does (broken for Claude):
tmux send-keys -t session "prompt" Enter  # Too fast!

# What conductor-mcp does (works):
tmux send-keys -t session "prompt"
sleep 0.8  # Wait for input detection
tmux send-keys -t session Enter
```

## Installation

```bash
# Install dependencies
pip install mcp edge-tts

# Add to Claude Code settings
claude mcp add conductor-mcp -- python /path/to/conductor-mcp/server.py
```

## Requirements

- Python 3.10+
- tmux 3.0+
- edge-tts (`pip install edge-tts`)
- mpv (for audio playback)
- beads CLI (optional, for spawn_worker context injection)

## Usage with Claude Code

Once configured, Claude can orchestrate workers:

### Basic: Separate Sessions
```python
# Spawn a worker for a beads issue (creates new tmux session)
spawn_worker(issue_id="BD-abc", project_dir="/path/to/project")

# Send a prompt (with proper delay)
send_prompt(session="BD-abc", text="Fix the auth bug. When done: bd close BD-abc")

# Announce status
speak(text="Worker spawned for BD-abc")

# Check worker status
status = get_worker_status(session="BD-abc")

# Clean up when done
kill_worker(session="BD-abc")
```

### Advanced: Visual Grid of Workers
Start with one fullscreen terminal and let Claude split it into a grid:

```python
# Create a 2x2 grid (4 panes)
grid = create_grid(layout="2x2", start_dir="/path/to/project")
# Returns: {"panes": ["%0", "%1", "%2", "%3"], "count": 4}

# Get 4 ready issues from beads
issues = ["BD-abc", "BD-def", "BD-ghi", "BD-jkl"]

# Spawn a worker in each pane
for pane_id, issue_id in zip(grid["panes"], issues):
    spawn_worker_in_pane(
        pane_id=pane_id,
        issue_id=issue_id,
        project_dir="/path/to/project"
    )
    speak(text=f"Spawned {issue_id}")

# Monitor all panes
panes = list_panes()
for pane in panes:
    print(f"{pane['pane_id']}: {pane['claude_status'] or 'unknown'}")
```

This creates a visual dashboard where you can watch all workers simultaneously.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code                                                    │
├─────────────────────────────────────────────────────────────────┤
│  MCP Servers:                                                   │
│  ├── beads       → issue tracking                               │
│  ├── tmux        → basic session management                     │
│  └── conductor   → orchestration superpowers                    │
└─────────────────────────────────────────────────────────────────┘
```

## Reference

Based on proven patterns from:
- TabzChrome (MCP tools with 800ms delay)
- Legacy claude-hooks (audio-announcer.sh, state-tracker.sh)
- BeadsHive conductor workflows

## License

MIT
