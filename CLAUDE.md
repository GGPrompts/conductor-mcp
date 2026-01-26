# conductor-mcp

MCP server providing orchestration tools for Claude Code workers.

## Tools

| Tool | Purpose |
|------|---------|
| `send_prompt` | Send text to tmux session with delay for Claude prompt submission |
| `spawn_worker` | Create worktree + tmux session + inject beads context |
| `speak` | TTS announcements via edge-tts |
| `kill_worker` | Terminate worker session |
| `list_workers` | List active tmux sessions |
| `get_worker_status` | Read Claude state from /tmp/claude-code-state |
| `capture_worker_output` | Get recent terminal output |

## Key Pattern: The Delay Fix

The critical feature is `send_prompt`'s delay between text and Enter:

```python
tmux send-keys -t session "text"
sleep 0.8  # Wait for Claude's input detection
tmux send-keys -t session Enter
```

Without this delay, Claude creates a newline instead of submitting.

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
