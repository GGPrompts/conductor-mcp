# Model Arena

Run blind comparison challenges across AI models using conductor-mcp orchestration.

## Usage

```
/arena                           # Interactive setup
/arena "custom prompt here"      # Quick start with custom prompt
```

## Interactive Setup

### 1. Select Contestants (pick 4)

| Contestant | Description |
|------------|-------------|
| `claude` | Claude Code vanilla |
| `claude+skill` | Claude Code with skill prefix (e.g., `/frontend-design`) |
| `codex` | OpenAI Codex CLI |
| `gemini` | Google Gemini CLI |
| `copilot` | GitHub Copilot CLI |

Default: `claude`, `claude+skill`, `codex`, `gemini`

### 2. Prompt Complexity

| Level | Examples |
|-------|----------|
| Simple | Bouncing ball, color picker, animated gradient |
| Medium | Snake game, markdown editor, todo app |
| Complex | Metaball lava lamp, particle physics, 3D transforms |
| Style Guide | Design systems, theme builders, component libraries |
| Custom | User provides prompt |

**Style Guide prompts:**
- "Create a complete design system with color palette, typography scale, spacing, and component examples"
- "Build a dark/light theme system with CSS variables, toggle, and live previews"
- "Design a neo-brutalist style guide with buttons, cards, forms, and layouts"

### 3. Skill Selection (for claude+skill)

If `claude+skill` is a contestant, ask which skill to use:
- `/frontend-design` (recommended for UI challenges)
- `/ui-styling`
- Custom skill path

### 4. Confirm & Execute

```
Contestants: Claude, Claude+frontend-design, Codex, Gemini
Prompt: "Create a design system style guide..."
Skill: /frontend-design

[Start Arena]
```

## Execution

Use conductor-mcp tools for all orchestration.

### 1. Setup Challenge Directory

```bash
ARENA_DIR=~/projects/model-arena/challenges
CHALLENGE_ID=$(printf "%03d" $(($(ls -1 "$ARENA_DIR" 2>/dev/null | wc -l) + 1)))-$SLUG
mkdir -p "$ARENA_DIR/$CHALLENGE_ID"/{a,b,c,d}
```

### 2. Create Grid Layout

Use `conductor/create_grid` to create a 2x2 layout:

```
┌─────────────────┬─────────────────┐
│    Pane A       │    Pane B       │
├─────────────────┼─────────────────┤
│    Pane C       │    Pane D       │
└─────────────────┴─────────────────┘
```

Call: `create_grid` with `layout: "2x2"`

### 3. Get Pane IDs

Use `conductor/list_panes` to get the 4 pane IDs.

### 4. Start Watches

For each pane, use `conductor/watch_pane` to stream output to files:
- `/tmp/arena-{challenge_id}-a.log`
- `/tmp/arena-{challenge_id}-b.log`
- etc.

### 5. Spawn Contestants

Shuffle contestant order randomly for blind comparison. Record mapping in memory.

For each pane, use `conductor/send_prompt` with the appropriate command:

| Contestant | Command |
|------------|---------|
| claude | `claude "{prompt}"` |
| claude+skill | `claude "/{skill} {prompt}"` |
| codex | `codex --full-auto "{prompt}"` |
| gemini | `gemini -i "{prompt}" -y` |
| copilot | `copilot --allow-all-tools "{prompt}"` |

Arena rules appended to all prompts:
```
Create this in a single index.html file. Self-contained, inline CSS/JS, no external dependencies.
```

### 6. Announce Start

Use `conductor/speak` to announce: "Arena started with 4 contestants"

### 7. Monitor Progress

Periodically use `conductor/read_watch` on each pane to check for completion.

Completion indicators:
- File `index.html` exists in working directory
- Output contains "Done" or prompt returns
- Pane shows shell prompt (command finished)

### 8. Collect Results

When all complete:

1. Stop watches with `conductor/stop_watch`
2. Copy outputs to anonymized files:
   ```bash
   cp "$ARENA_DIR/$CHALLENGE_ID/a/index.html" "$ARENA_DIR/$CHALLENGE_ID/a.html"
   # etc for b, c, d
   ```
3. Create `meta.json` with blind mapping:
   ```json
   {
     "id": "001-style-guide",
     "prompt": "...",
     "contestants": ["claude", "claude+frontend-design", "codex", "gemini"],
     "answers": {"a": "gemini", "b": "claude", "c": "codex", "d": "claude+frontend-design"}
   }
   ```

### 9. Announce Complete

Use `conductor/speak`: "Arena complete. 4 entries ready for judging."

Use `conductor/show_popup` to display summary.

## CLI Reference

| CLI | Auto Mode |
|-----|-----------|
| claude | `claude "prompt"` |
| claude+skill | `claude "/skill prompt"` |
| codex | `codex --full-auto "prompt"` |
| gemini | `gemini -i "prompt" -y` |
| copilot | `copilot --allow-all-tools "prompt"` |

## Conductor Tools Used

| Tool | Purpose |
|------|---------|
| `create_grid` | Create 2x2 pane layout |
| `list_panes` | Get pane IDs |
| `send_prompt` | Launch CLI in each pane |
| `watch_pane` | Stream output to files |
| `read_watch` | Check progress |
| `stop_watch` | End monitoring |
| `speak` | TTS announcements |
| `show_popup` | Display results |
