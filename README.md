# conductor-mcp

A lightweight MCP server for orchestrating Claude Code workers from any terminal.

**No Chrome required.** Brings TabzChrome's orchestration superpowers to iTerm, Kitty, Alacritty, Windows Terminal, WezTerm, or any terminal you prefer.

## Features (33 Tools)

### Core Worker Tools
| Tool | Description |
|------|-------------|
| `send_prompt` | Send text to Claude/Codex with proper delay for submission |
| `spawn_worker` | Create worktree + tmux session + inject beads context |
| `speak` | TTS announcements via edge-tts (with audio mutex) |
| `kill_worker` | Clean up worker session and optionally worktree |
| `list_workers` | List active worker sessions |
| `get_worker_status` | Read Claude state from /tmp/claude-code-state |
| `capture_worker_output` | Get recent terminal output |

### Session & Window Management
| Tool | Description |
|------|-------------|
| `create_session` | Create new tmux session (for non-tmux contexts like Claude Desktop) |
| `create_window` | Create new window in existing session |

### Pane Management
| Tool | Description |
|------|-------------|
| `split_pane` | Split current pane horizontally or vertically |
| `create_grid` | Create grid layout (2x2, 3x1, 4x1, etc.) |
| `list_panes` | List all panes with their status |
| `focus_pane` | Switch focus to a specific pane |
| `kill_pane` | Kill a specific pane |
| `spawn_worker_in_pane` | Spawn a worker in an existing pane |

### Real-time Monitoring
| Tool | Description |
|------|-------------|
| `watch_pane` | Stream pane output to file via pipe-pane |
| `stop_watch` | Stop streaming pane output |
| `read_watch` | Read recent output from watch file |

### Synchronization
| Tool | Description |
|------|-------------|
| `wait_for_signal` | Block until channel receives signal (with timeout) |
| `send_signal` | Send signal on channel to unblock waiters |

### Popup Notifications
| Tool | Description |
|------|-------------|
| `show_popup` | Display floating popup in tmux |
| `show_status_popup` | Show worker status summary popup |

### Hooks (Event-driven)
| Tool | Description |
|------|-------------|
| `set_pane_hook` | Set command to run on pane events (died, exited, etc.) |
| `clear_hook` | Remove a previously set hook |
| `list_hooks` | List active hooks |

### Layout & Resizing
| Tool | Description |
|------|-------------|
| `resize_pane` | Resize pane (absolute or relative) |
| `zoom_pane` | Toggle fullscreen zoom for pane |
| `apply_layout` | Apply layout (tiled, even-horizontal, etc.) |
| `rebalance_panes` | Rebalance panes to equal sizes |

### Configuration
| Tool | Description |
|------|-------------|
| `get_config` | Get current conductor configuration |
| `set_config` | Update configuration settings |
| `list_voices` | List available TTS voices with assignments |
| `test_voice` | Test a specific TTS voice |
| `reset_voice_assignments` | Clear all worker voice assignments |

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
# Clone the repo
git clone https://github.com/GGPrompts/conductor-mcp.git
cd conductor-mcp

# Install dependencies
pip install mcp edge-tts

# Add to Claude Code
claude mcp add conductor -- python /path/to/conductor-mcp/server.py
```

## Requirements

- Python 3.10+
- tmux 3.0+
- edge-tts (`pip install edge-tts`)
- mpv, ffplay, or vlc (for audio playback)
- beads CLI (optional, for spawn_worker context injection)
- git (for worktree management)

## Audio Hooks Setup (Optional)

For automatic TTS announcements when Claude uses tools or finishes tasks:

### 1. Copy hook scripts

```bash
mkdir -p ~/.claude/hooks/scripts
cp reference/state-tracker.sh ~/.claude/hooks/scripts/
cp reference/audio-announcer.sh ~/.claude/hooks/scripts/
chmod +x ~/.claude/hooks/scripts/*.sh
```

### 2. Add to Claude settings (~/.claude/settings.json)

```json
{
  "env": {
    "CLAUDE_AUDIO": "1",
    "CLAUDE_VOICE": "en-US-AndrewNeural",
    "CLAUDE_RATE": "+20%"
  },
  "hooks": {
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/hooks/scripts/state-tracker.sh session-start", "timeout": 2}]}],
    "PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/hooks/scripts/state-tracker.sh pre-tool", "timeout": 1}]}],
    "PostToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/hooks/scripts/state-tracker.sh post-tool", "timeout": 1}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "~/.claude/hooks/scripts/state-tracker.sh stop", "timeout": 1}]}]
  }
}
```

### 3. Available voices

The conductor assigns unique voices to workers automatically. Available voices:
- US: AriaNeural, GuyNeural, JennyNeural, DavisNeural, AmberNeural, AndrewNeural, EmmaNeural, BrianNeural
- UK: SoniaNeural, RyanNeural
- AU: NatashaNeural, WilliamNeural

### Audio features
- **Mutex**: Direct `speak()` calls take priority over hook announcements
- **Debounce**: Rapid tool announcements are throttled
- **Caching**: Generated audio is cached in `/tmp/claude-audio-cache/`

## Usage Examples

### Basic: Send prompts to workers
```python
# Send a prompt with proper delay
send_prompt(session="worker-1", text="Fix the auth bug")

# Announce status
speak(text="Task assigned to worker 1")
```

### Visual Grid of Workers
```python
# Create a 2x2 grid (4 panes)
grid = create_grid(layout="2x2", start_dir="/path/to/project")

# Spawn workers in each pane
for pane_id, issue_id in zip(grid["panes"], issues):
    spawn_worker_in_pane(pane_id=pane_id, issue_id=issue_id, project_dir="/path/to/project")
    speak(text=f"Spawned {issue_id}")
```

### From Claude Desktop (non-tmux)
```python
# Bootstrap tmux environment first
session = create_session(name="workers", start_dir="/project")

# Then create grid and spawn workers
create_grid(layout="2x2", session="workers")
```

### Real-time Monitoring
```python
# Watch a pane's output
watch_pane(pane_id="%5")

# Read recent output
output = read_watch(pane_id="%5", lines=20)

# Stop watching
stop_watch(pane_id="%5")
```

### Worker Coordination with Signals
```python
# Conductor waits for worker to finish
result = await wait_for_signal(channel="done-BD-abc", timeout_s=600)

# Worker signals completion
send_signal(channel="done-BD-abc")
```

## Reference

Legacy implementations in `reference/`:
- `audio-announcer.sh` - TTS with caching, mutex, debounce
- `state-tracker.sh` - Claude hook for state tracking
- `tmux-status-claude.sh` - Tmux status bar integration

## License

MIT
