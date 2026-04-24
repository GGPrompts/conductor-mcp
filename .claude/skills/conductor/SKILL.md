---
name: help
description: Interactive help menu for conductor-mcp — quick reference, settings, profiles, and hotkeys
user_invocable: true
command_name: conductor:help
---

# Conductor Help

You are the conductor help system. Present an interactive menu and handle the user's choice.

> **Prefer `cm` CLI over MCP shims.** After cm-aax, 29 of the 34 conductor MCP tools are thin shims over `conductor.core`. Calling them from inside a skill drags the MCP tool definition into the turn's context. Use `cm <verb>` via Bash instead — structured output is available on every verb via `--json`. Only five MCP tools remain canonical: `spawn_worker`, `smart_spawn`, `smart_spawn_wave`, `wait_for_signal`, `send_signal`.

## Step 1: Show Menu

Use `AskUserQuestion` to present this menu:

**Question:** "What would you like help with?"
**Header:** "Help topic"
**Options:**
1. **Quick Reference** — "Browse all conductor tools and common workflows"
2. **Settings** — "View current conductor configuration"
3. **Profiles** — "Manage spawn profiles (claude, codex, gemini, tfe, etc.)"
4. **Hotkeys** — "tmux keybinding cheat sheet"

## Step 2: Handle Selection

### Quick Reference

1. Read the reference files:
   - `references/tool-reference.md` (relative to this skill)
   - `references/workflows.md` (relative to this skill)
2. Present the content as formatted tables to the user
3. Ask if they want details on a specific tool or workflow

### Settings

1. Run `cm config get --json` via Bash to get the current configuration
2. Present settings in a formatted table:
   - Max workers, default layout, default dir
   - Voice: name, rate, pitch, random per worker
   - Delays: send_keys_ms, claude_boot_s
3. Tell the user that voice, profiles, delays, and default dir are edited in the conductor-tui Settings panel (cm-3gw): open conductor-tui (`Ctrl+b o` in tmux, or run `conductor-tui`) and cycle the top panel with `1` until the Settings tab is active. Canonical config: `~/.config/conductor/config.json`.

### Profiles

Profile CRUD (add / edit / remove) and the default-dir fallback now live in the conductor-tui Settings panel (cm-3gw). Tell the user: open conductor-tui (`Ctrl+b o` in tmux, or run `conductor-tui`), cycle the top panel with `1` to the Settings tab, and edit profiles there. For a quick read-only view from the CLI, run `cm config get --json | jq .profiles`.

### Hotkeys

1. Read `references/hotkeys.md` (relative to this skill)
2. Present the keybinding tables to the user
3. Mention they can customize prefix in their tmux.conf
