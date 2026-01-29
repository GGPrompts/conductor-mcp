# conductor-mcp

MCP server providing orchestration tools for Claude Code workers.

## Requirements

- **tmux** - Terminal multiplexer (pane/session management)
- **edge-tts** - Text-to-speech (`pip install edge-tts`)
- **Audio player** - mpv, ffplay, or vlc for TTS playback
- **bd** (optional) - Beads CLI for issue tracking integration
- **git** - For worktree management

## Tools (35 total)

### Core Worker Tools

| Tool | Purpose |
|------|---------|
| `send_keys` | Send keys to tmux session, optionally submit with Enter |
| `spawn_worker` | Create worktree + tmux session + inject beads context |
| `speak` | TTS announcements via edge-tts |
| `kill_worker` | Terminate worker session |
| `list_workers` | List active tmux sessions |
| `get_worker_status` | Read Claude state from /tmp/claude-code-state |
| `capture_worker_output` | Get recent terminal output |
| `get_context_percent` | Parse context % from Claude Code status line |
| `get_workers_with_capacity` | Find workers below context threshold for reuse |

### Session & Window Management

| Tool | Purpose |
|------|---------|
| `create_session` | Create new tmux session (for non-tmux contexts like Claude Desktop) |
| `create_window` | Create new window in existing session |

### Pane Management

| Tool | Purpose |
|------|---------|
| `split_pane` | Split current/target pane horizontally or vertically |
| `create_grid` | Create NxM grid layout (e.g., "2x2", "4x1") |
| `list_panes` | List all panes with status info |
| `focus_pane` | Switch focus to specific pane |
| `kill_pane` | Kill a specific pane |
| `spawn_worker_in_pane` | Launch worker in existing pane |

### Real-time Monitoring

| Tool | Purpose |
|------|---------|
| `watch_pane` | Stream pane output to file via pipe-pane |
| `stop_watch` | Stop streaming pane output |
| `read_watch` | Read recent output from watch file |

### Synchronization

| Tool | Purpose |
|------|---------|
| `wait_for_signal` | Block until channel receives signal (with timeout) |
| `send_signal` | Send signal on channel to unblock waiters |

### Popup Notifications

| Tool | Purpose |
|------|---------|
| `show_popup` | Display floating popup in tmux |
| `show_status_popup` | Show worker status summary popup |

### Hooks

| Tool | Purpose |
|------|---------|
| `set_pane_hook` | Set command to run on pane events (died, exited, etc.) |
| `clear_hook` | Remove a previously set hook |
| `list_hooks` | List active hooks |

### Layout & Resizing

| Tool | Purpose |
|------|---------|
| `resize_pane` | Resize pane (absolute or relative) |
| `zoom_pane` | Toggle fullscreen zoom for pane |
| `apply_layout` | Apply layout (tiled, even-horizontal, etc.) |
| `rebalance_panes` | Rebalance panes to equal sizes |

### Configuration

| Tool | Purpose |
|------|---------|
| `get_config` | Get current conductor configuration |
| `set_config` | Update configuration settings |
| `list_voices` | List available TTS voices with assignments |
| `test_voice` | Test a specific TTS voice |
| `reset_voice_assignments` | Clear all worker voice assignments |

## Key Pattern: The Delay Fix

The `send_keys` tool handles the timing automatically:

```python
# Submit with delay (default)
send_keys(session, "text")  # submit=True by default

# Just type without submitting
send_keys(session, "partial", submit=False)

# Internally when submit=True:
#   tmux send-keys -t session "text"
#   sleep 0.8  # Wait for Claude's input detection
#   tmux send-keys -t session Enter
```

Without the delay, Claude creates a newline instead of submitting.

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run server directly
python server.py

# Test with Claude Code
claude mcp add conductor -- python /path/to/server.py
```

## Reference

Legacy implementations in `reference/`:
- `audio-announcer.sh` - Original TTS with caching, mutex, debounce
- `state-tracker.sh` - Claude hook for state tracking
- `tmux-status-claude.sh` - Tmux status bar integration

## Beads Issue

Tracked as BeadsHive-uz3
