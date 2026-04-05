# conductor-tui

Go TUI companion for conductor-mcp. Provides a visual session manager and settings panel.

Ported from ~/projects/tmuxplexer — a Bubble Tea (charmbracelet) application.

## Build & Run

```bash
cd tui
go build -o conductor-tui .
./conductor-tui          # fullscreen mode
./conductor-tui --popup  # popup mode (for tmux Ctrl+b o binding)
```

## Architecture

- **Framework**: Bubble Tea (Elm-style MVC) + Lipgloss styling
- **Module**: `github.com/ggprompts/conductor-tui`
- **Config**: `~/.config/conductor-tui/config.yaml` (app settings), `~/.config/conductor-tui/templates.json` (tmux templates)

## Key Files

| File | Purpose |
|------|---------|
| `main.go` | Entry point, CLI flags (`--popup`, `--preview`) |
| `types.go` | All structs (Model, Config, TmuxSession, templates) |
| `model.go` | Initialization, layout calculations, session loading |
| `view.go` | 3-panel rendering (sessions, preview, command) |
| `update.go` | Message dispatcher |
| `update_keyboard.go` | Keyboard input handling |
| `update_mouse.go` | Mouse/click handling |
| `styles.go` | Lipgloss color/style definitions |
| `config.go` | YAML config loading |
| `templates.go` | Template CRUD |
| `tmux.go` | Tmux command wrappers |
| `claude_state.go` | State file reading, status formatting, context % display |

## State Integration

Reads `/tmp/claude-code-state/*.json` — the same state files written by conductor-mcp's hooks in `plugins/conductor/hooks/scripts/state-tracker.sh`. Shows live worker status (idle, processing, tool_use, awaiting_input) with context % and tool details.

## UI Layout

```
┌─────────────────────────────────┐
│ Sessions [1] | Templates        │  Panel 1: session list with Claude status
├─────────────────────────────────┤
│ Preview                         │  Panel 2: live tmux scrollback
├─────────────────────────────────┤
│ Command                         │  Panel 3: send commands to AI sessions
└─────────────────────────────────┘
```

- Press `1`/`2`/`3` to focus panels
- Press `1` again when focused to toggle Sessions/Templates tabs
- `Enter` attaches to session, `d` kills, `s` saves as template

## Popup Mode

Launched via tmux keybinding: `tmux popup -E -w 80% -h 80% conductor-tui --popup`

In popup mode, `Enter` uses `tmux switch-client` (stays in tmux) instead of `attach-session`.
