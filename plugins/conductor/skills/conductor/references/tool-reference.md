# Conductor Tool Reference

## Core Worker Tools

| Tool | Purpose |
|------|---------|
| `send_keys(session, keys, submit?, delay_ms?)` | Send keys to tmux session, optionally press Enter |
| `spawn_worker(issue_id, project_dir, profile_cmd?, inject_context?)` | Create detached worktree + tmux session |
| `speak(text, voice?, rate?, worker_id?, blocking?, priority?)` | TTS via edge-tts with audio mutex |
| `kill_worker(session, cleanup_worktree?, project_dir?)` | Kill session + optional worktree cleanup |
| `list_workers()` | List active tmux sessions with Claude status |
| `get_worker_status(session)` | Read Claude state from /tmp/claude-code-state |
| `capture_worker_output(session, lines?)` | Get recent terminal output from pane |
| `get_context_percent(target)` | Get context usage % (state file or terminal scrape) |
| `get_workers_with_capacity(threshold?)` | Find workers below context threshold for reuse |

## Smart Spawn (Visible Placement)

| Tool | Purpose |
|------|---------|
| `smart_spawn(issue_id, project_dir?, profile?, ...)` | Auto-split pane + spawn worker visibly |
| `smart_spawn_wave(issue_ids, project_dir?, profile?, ...)` | Spawn multiple workers with auto-splitting |

**Profile support:** Both accept `profile="name"` to use a configured profile (claude, codex, gemini, tfe, lazygit). Falls back to `profile_cmd` for raw commands.

## Session & Window Management

| Tool | Purpose |
|------|---------|
| `create_session(name, start_dir?, command?, attach?)` | Create new tmux session |
| `create_window(session, name?, start_dir?, command?)` | Add window to existing session |

## Pane Management

| Tool | Purpose |
|------|---------|
| `split_pane(direction?, target?, percentage?, start_dir?)` | Split pane horizontally or vertically |
| `create_grid(layout?, session?, start_dir?)` | Create NxM grid (e.g., "2x2", "3x1") |
| `list_panes(session?)` | List all panes with size, command, status |
| `focus_pane(pane_id)` | Switch focus to specific pane |
| `kill_pane(pane_id)` | Kill a specific pane |
| `spawn_worker_in_pane(pane_id, issue_id, project_dir, ...)` | Launch worker in existing pane |

## Real-time Monitoring

| Tool | Purpose |
|------|---------|
| `watch_pane(pane_id, output_file?)` | Stream pane output to file via pipe-pane |
| `stop_watch(pane_id)` | Stop streaming |
| `read_watch(pane_id, lines?, output_file?)` | Read recent output from watch file |

## Synchronization

| Tool | Purpose |
|------|---------|
| `wait_for_signal(channel, timeout_s?)` | Block until signal received (default 5min) |
| `send_signal(channel)` | Unblock waiters on a channel |

## Popup Notifications

| Tool | Purpose |
|------|---------|
| `show_popup(message, title?, width?, height?, duration_s?, target?)` | Floating tmux popup |
| `show_status_popup(workers?, target?)` | Worker status summary popup |

## Hooks

| Tool | Purpose |
|------|---------|
| `set_pane_hook(event, command, session?)` | Run command on pane events |
| `clear_hook(event, session?)` | Remove a hook |
| `list_hooks(session?)` | List active hooks |

## Layout & Resizing

| Tool | Purpose |
|------|---------|
| `resize_pane(pane_id, width?, height?, adjust_x?, adjust_y?)` | Resize absolute or relative |
| `zoom_pane(pane_id)` | Toggle fullscreen zoom |
| `apply_layout(layout, target?)` | Apply layout (tiled, even-horizontal, etc.) |
| `rebalance_panes(target?)` | Rebalance panes to equal sizes |

## Configuration & Profiles

| Tool | Purpose |
|------|---------|
| `get_config()` | Get current configuration |
| `set_config(...)` | Update settings (max_workers, default_dir, voice, delays) |
| `add_profile(name, command, dir?)` | Add or update spawn profile |
| `remove_profile(name)` | Delete spawn profile |
| `list_profiles()` | Show all profiles with resolved dirs |
| `list_voices()` | List TTS voices with assignments |
| `test_voice(voice, text?)` | Test a TTS voice |
| `reset_voice_assignments()` | Clear all voice assignments |
