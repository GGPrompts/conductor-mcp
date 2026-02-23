# conductor-mcp

MCP server providing orchestration tools for Claude Code workers.

## Requirements

- **tmux** - Terminal multiplexer (pane/session management)
- **edge-tts** - Text-to-speech (`pip install edge-tts`)
- **Audio player** - mpv, ffplay, or vlc for TTS playback
- **bd** (optional) - Beads CLI for issue tracking integration
- **git** - For worktree management

## Tools (41 total)

### Core Worker Tools (9)

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

### Smart Spawn (2)

| Tool | Purpose |
|------|---------|
| `smart_spawn` | Auto-split pane + spawn worker visibly, with profile support |
| `smart_spawn_wave` | Spawn multiple workers with auto-splitting |

### Session & Window Management (2)

| Tool | Purpose |
|------|---------|
| `create_session` | Create new tmux session (for non-tmux contexts like Claude Desktop) |
| `create_window` | Create new window in existing session |

### Pane Management (6)

| Tool | Purpose |
|------|---------|
| `split_pane` | Split current/target pane horizontally or vertically |
| `create_grid` | Create NxM grid layout (e.g., "2x2", "4x1") |
| `list_panes` | List all panes with status info |
| `focus_pane` | Switch focus to specific pane |
| `kill_pane` | Kill a specific pane |
| `spawn_worker_in_pane` | Launch worker in existing pane |

### Real-time Monitoring (3)

| Tool | Purpose |
|------|---------|
| `watch_pane` | Stream pane output to file via pipe-pane |
| `stop_watch` | Stop streaming pane output |
| `read_watch` | Read recent output from watch file |

### Synchronization (2)

| Tool | Purpose |
|------|---------|
| `wait_for_signal` | Block until channel receives signal (with timeout) |
| `send_signal` | Send signal on channel to unblock waiters |

### Popup Notifications (2)

| Tool | Purpose |
|------|---------|
| `show_popup` | Display floating popup in tmux |
| `show_status_popup` | Show worker status summary popup |

### Hooks (3)

| Tool | Purpose |
|------|---------|
| `set_pane_hook` | Set command to run on pane events (died, exited, etc.) |
| `clear_hook` | Remove a previously set hook |
| `list_hooks` | List active hooks |

### Layout & Resizing (4)

| Tool | Purpose |
|------|---------|
| `resize_pane` | Resize pane (absolute or relative) |
| `zoom_pane` | Toggle fullscreen zoom for pane |
| `apply_layout` | Apply layout (tiled, even-horizontal, etc.) |
| `rebalance_panes` | Rebalance panes to equal sizes |

### Profiles (3)

| Tool | Purpose |
|------|---------|
| `add_profile` | Add/update a spawn profile (name, command, optional pinned dir) |
| `remove_profile` | Delete a spawn profile |
| `list_profiles` | List all profiles with resolved directories |

### Configuration (5)

| Tool | Purpose |
|------|---------|
| `get_config` | Get current conductor configuration |
| `set_config` | Update settings (max_workers, default_dir, voice, delays) |
| `list_voices` | List available TTS voices with assignments |
| `test_voice` | Test a specific TTS voice |
| `reset_voice_assignments` | Clear all worker voice assignments |

## Default Profiles & Spawnable Tools

Profiles are stored in config and used by `smart_spawn(profile="name")`.

### AI Coding Agents

| Profile | Command | Use For |
|---------|---------|---------|
| `claude` | `claude` | Default. Full agentic coding with MCP support |
| `codex` | `codex` | OpenAI Codex CLI agent |
| `gemini` | `gemini -i` | Google Gemini CLI (interactive mode) |
| `copilot` | `copilot` | GitHub Copilot CLI |

#### Codex Modes

| Command | Mode |
|---------|------|
| `codex` | Interactive (default) |
| `codex review` | Code review only — no file changes |
| `codex --full-auto` | Auto-approve with sandbox (`-a on-request --sandbox workspace-write`) |
| `codex -a never` | Never ask for approval |
| `codex -m o3` | Use a specific model |
| `codex -s read-only` | Read-only sandbox (safest) |

#### Copilot Models

| Model | Notes |
|-------|-------|
| `gpt-5-mini` | Lightweight, unlimited usage on most plans |
| `gpt-4.1` | Lightweight, unlimited usage on most plans |
| `gpt-5` | Standard |
| `gpt-5.1` / `gpt-5.2` | Newer GPT models |
| `gpt-5.1-codex` / `gpt-5.2-codex` / `gpt-5.3-codex` | Code-optimized |
| `gpt-5.1-codex-mini` | Code-optimized lightweight |
| `gpt-5.1-codex-max` | Premium code model |
| `claude-haiku-4.5` | Lightweight Claude via Copilot |
| `claude-sonnet-4` / `claude-sonnet-4.5` | Mid-tier Claude via Copilot |
| `claude-opus-4.5` / `claude-opus-4.6` | Top-tier Claude via Copilot |
| `gemini-3-pro-preview` | Google Gemini via Copilot |

Usage: `copilot --model gpt-5-mini` or `copilot --model claude-haiku-4.5 --yolo`

#### Gemini Modes

| Command | Mode |
|---------|------|
| `gemini -i` | Interactive (default profile) |
| `gemini -y` | YOLO mode — auto-approve all operations |
| `gemini -m 2.5-pro` | Use a specific model |

### TUI Tools

| Profile | Command | Use For |
|---------|---------|---------|
| `tfe` | `tfe` | Terminal file explorer with markdown preview |
| `lazygit` | `lazygit` | Terminal git UI |

### Opening Files for Review

After editing markdown, config, or design docs, open them for human review:

```python
# Split a pane and open TFE with file preview
split_pane(direction="horizontal")
send_keys(new_pane_id, "tfe /path/to/CLAUDE.md --preview")
```

TFE renders markdown beautifully and supports `--preview` to auto-open the preview pane with the file selected.

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
