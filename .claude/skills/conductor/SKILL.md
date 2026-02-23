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
2. **Settings** — "View and adjust conductor configuration"
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

1. Call `get_config()` via MCP to get current configuration
2. Present settings in a formatted table:
   - Max workers, default layout, default dir
   - Voice: name, rate, pitch, random per worker
   - Delays: send_keys_ms, claude_boot_s
3. Use `AskUserQuestion` to ask what they'd like to change:
   - **Max workers** — "Change concurrent worker limit"
   - **Voice settings** — "Change TTS voice, speed, or pitch"
   - **Delays** — "Adjust send_keys or boot timing"
   - **Default directory** — "Set fallback project directory"
4. Apply changes with `set_config()`

### Profiles

1. Call `list_profiles()` via MCP to get current profiles
2. Present profiles in a table: name | command | pinned dir | effective dir
3. Use `AskUserQuestion` to ask what they'd like to do:
   - **Add/edit profile** — "Create or update a spawn profile"
   - **Remove profile** — "Delete an existing profile"
   - **Set default dir** — "Set global fallback directory for all profiles"
   - **Test spawn** — "Test a profile with a dry run description"
4. For add/edit: ask for name, command, and optional pinned dir, then call `add_profile()`
5. For remove: ask which profile, then call `remove_profile()`
6. For default dir: ask for path, then call `set_config(default_dir=...)`

### Hotkeys

1. Read `references/hotkeys.md` (relative to this skill)
2. Present the keybinding tables to the user
3. Mention they can customize prefix in their tmux.conf
