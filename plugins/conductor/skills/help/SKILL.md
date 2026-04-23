---
name: help
description: Interactive help menu for conductor-mcp — quick reference, settings, profiles, and hotkeys
user_invocable: true
command_name: conductor:help
---

# Conductor Help

You are the conductor help system. Present an interactive menu and handle the user's choice.

## Step 1: Show Menu

Use `AskUserQuestion` to present this menu:

**Question:** "What would you like help with?"
**Header:** "Help topic"
**Options:**
1. **Quick Reference** — "Browse all conductor tools and common workflows"
2. **Settings** — "Where to adjust conductor configuration"
3. **Profiles** — "Where to manage spawn profiles (claude, codex, gemini, tfe, etc.)"
4. **Hotkeys** — "tmux keybinding cheat sheet"

## Step 2: Handle Selection

### Quick Reference

1. Read the reference files:
   - `references/tool-reference.md` (relative to the conductor skill in this plugin)
   - `references/workflows.md` (relative to the conductor skill in this plugin)
2. Present the content as formatted tables to the user
3. Ask if they want details on a specific tool or workflow

### Settings

Settings (voice, layout, timing) now live in the conductor-tui Settings panel.
Tell the user:

- Open conductor-tui (`Ctrl+b o` in tmux for the popup, or run `conductor-tui` directly)
- Press `1` repeatedly in the top panel to cycle: Sessions → Templates → Settings
- The Settings tab has sections for Voice, Profiles, and Layout/Timing

For a read-only peek at current config, call `get_config()` via MCP.

The canonical config lives at `~/.config/conductor/config.json` and is shared by the MCP server and the TUI.

### Profiles

Profiles (claude, codex, gemini, tfe, lazygit, copilot, etc.) are managed from the conductor-tui Settings panel:

- Open conductor-tui and cycle to the Settings tab (press `1` until the Settings tab is active)
- Switch to the Profiles sub-section with `Tab`
- View the list of configured profiles

For now, creating/editing profiles is still easiest by editing `~/.config/conductor/config.json` directly (full CRUD in the TUI is a follow-up). Claude continues to consume profiles via `smart_spawn(profile="name")`.

### Hotkeys

1. Read `references/hotkeys.md` (relative to the conductor skill in this plugin)
2. Present the keybinding tables to the user
3. Mention they can customize prefix in their tmux.conf
