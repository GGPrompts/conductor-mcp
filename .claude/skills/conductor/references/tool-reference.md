# Conductor Tool Reference

> **Prefer `cm` CLI over MCP.** Post-cm-aax, most verbs ship as `cm <verb>` plus a thin MCP shim for compatibility. Calling the `cm` CLI via Bash keeps tool definitions out of the turn's MCP registry footprint. Every `cm` verb supports `--json` for structured output; default is terse TSV (no header, one record per line).
>
> Five primitives stay MCP-only (marked **MCP**): `spawn_worker`, `smart_spawn`, `smart_spawn_wave`, `wait_for_signal`, `send_signal`. Everything else has a `cm` equivalent.

## Core Worker Tools

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Send keys to tmux session, optionally press Enter | `cm send <session> "<keys>" [--no-submit] [--delay-ms N]` | `send_keys` |
| Create detached worktree + tmux session | — | `spawn_worker` **(MCP)** |
| TTS via edge-tts with audio mutex | `cm speak "<text>" [--voice ...] [--rate ...] [--worker-id ...]` | `speak` |
| Kill session + optional worktree cleanup | `cm kill worker <session> [--cleanup-worktree --project-dir ...]` | `kill_worker` |
| List active tmux sessions with Claude status | `cm list workers` | `list_workers` |
| Read Claude state from /tmp/claude-code-state | `cm worker status <session>` | `get_worker_status` |
| Get recent terminal output from pane | `cm capture <session> [--lines N]` | `capture_worker_output` |
| Get context usage % (state file or terminal scrape) | `cm context <target>` | `get_context_percent` |
| Find workers below context threshold for reuse | `cm worker capacity [--threshold N]` | `get_workers_with_capacity` |

## Smart Spawn (Visible Placement) — MCP-only

| Purpose | MCP |
|---------|-----|
| Auto-split pane + spawn worker visibly | `smart_spawn(issue_id, project_dir?, profile?, ...)` |
| Spawn multiple workers with auto-splitting | `smart_spawn_wave(issue_ids, project_dir?, profile?, ...)` |

**Profile support:** Both accept `profile="name"` to use a configured profile (claude, codex, gemini, tfe, lazygit). Falls back to `profile_cmd` for raw commands.

## Session & Window Management

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Create new tmux session | `cm session new <name> [--start-dir ...] [--command ...] [--attach]` | `create_session` |
| Add window to existing session | `cm window new <session> [--name ...] [--start-dir ...] [--command ...]` | `create_window` |

## Pane Management

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Split pane horizontally or vertically | `cm split [--direction h|v] [--target ...] [--percentage N] [--start-dir ...]` | `split_pane` |
| Create NxM grid (e.g., "2x2", "3x1") | `cm grid <layout> [--session ...] [--start-dir ...]` | `create_grid` |
| List all panes with size, command, status | `cm list panes [--session ...]` | `list_panes` |
| Switch focus to specific pane | `cm focus <pane_id>` | `focus_pane` |
| Kill a specific pane | `cm kill pane <pane_id>` | `kill_pane` |
| Launch worker in existing pane | `cm spawn in-pane <pane_id> <issue_id> --project-dir ...` | `spawn_worker_in_pane` |

## Real-time Monitoring

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Stream pane output to file via pipe-pane | `cm watch start <pane_id> [--output-file ...]` | `watch_pane` |
| Stop streaming | `cm watch stop <pane_id>` | `stop_watch` |
| Read recent output from watch file | `cm watch read <pane_id> [--lines N] [--output-file ...]` | `read_watch` |

## Synchronization — MCP-only

| Purpose | MCP |
|---------|-----|
| Block until signal received (default 5min) | `wait_for_signal(channel, timeout_s?)` |
| Unblock waiters on a channel | `send_signal(channel)` |

## Popup Notifications

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Floating tmux popup | `cm popup show "<message>" [--title ...] [--width N] [--height N] [--duration-s N] [--target ...]` | `show_popup` |
| Worker status summary popup | `cm popup status [--workers ...] [--target ...]` | `show_status_popup` |

## Hooks

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Run command on pane events | `cm hook set <event> "<command>" [--session ...]` | `set_pane_hook` |
| Remove a hook | `cm hook clear <event> [--session ...]` | `clear_hook` |
| List active hooks | `cm hook list [--session ...]` | `list_hooks` |

## Layout & Resizing

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Resize absolute or relative | `cm resize <pane_id> [--width N] [--height N] [--adjust-x N] [--adjust-y N]` | `resize_pane` |
| Toggle fullscreen zoom | `cm zoom <pane_id>` | `zoom_pane` |
| Apply layout (tiled, even-horizontal, etc.) | `cm layout apply <name> [--target ...]` | `apply_layout` |
| Rebalance panes to equal sizes | `cm layout rebalance [--target ...]` | `rebalance_panes` |

## Configuration

| Purpose | CLI | MCP shim |
|---------|-----|----------|
| Get current configuration | `cm config get [--json]` | `get_config` |

Voice, profiles, delays, and default-dir are edited in the conductor-tui Settings panel (cm-3gw) — run `conductor-tui` or press `Ctrl+b o` in tmux, then cycle to the Settings tab with `1`. Canonical config file: `~/.config/conductor/config.json`.
