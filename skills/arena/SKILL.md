# Model Arena

Run a blind comparison challenge across multiple AI models in parallel.

## Usage

```
/arena "Create a lava lamp effect with metaballs"
```

## Available CLIs

| CLI | Model | Help |
|-----|-------|------|
| `claude` | Claude Code (Opus 4.5) | `claude --help` |
| `codex` | OpenAI Codex | `codex --help` |
| `copilot` | GitHub Copilot | `copilot --help` |
| `gemini` | Google Gemini | `gemini --help` |

## Workflow

### Phase 1: Discover Current Pane

First, find your current tmux pane (TabzChrome starts at 1):

```bash
# Get current pane info
tmux display-message -p '#{session_name}:#{window_index}.#{pane_index}'
```

### Phase 2: Setup Challenge Folder

```bash
ARENA_DIR=~/projects/model-arena
CHALLENGES_DIR=$ARENA_DIR/challenges

# Find next challenge number
NEXT_NUM=$(ls -1 "$CHALLENGES_DIR" | wc -l)
NEXT_NUM=$((NEXT_NUM + 1))
CHALLENGE_ID=$(printf "%03d" $NEXT_NUM)-$SLUG

# Create folder structure
mkdir -p "$CHALLENGES_DIR/$CHALLENGE_ID"/{claude,codex,copilot,gemini}
```

### Phase 3: Split Current Pane into Quad

Split your current pane into 4 (you stay in top-left):

```bash
# Get current pane
CURRENT=$(tmux display-message -p '#{pane_id}')

# Split right (creates pane for codex)
tmux split-window -h -t $CURRENT
CODEX_PANE=$(tmux display-message -p '#{pane_id}')

# Split the left side down (creates pane for copilot)
tmux select-pane -t $CURRENT
tmux split-window -v -t $CURRENT
COPILOT_PANE=$(tmux display-message -p '#{pane_id}')

# Split the right side down (creates pane for gemini)
tmux select-pane -t $CODEX_PANE
tmux split-window -v -t $CODEX_PANE
GEMINI_PANE=$(tmux display-message -p '#{pane_id}')

# Return focus to conductor pane
tmux select-pane -t $CURRENT
```

Result:
```
┌──────────────┬──────────────┐
│  Conductor   │    Codex     │
│  (claude)    │              │
├──────────────┼──────────────┤
│   Copilot    │   Gemini     │
│              │              │
└──────────────┴──────────────┘
```

### Phase 4: Spawn Models with Prompts

Each CLI needs its prompt passed correctly. Check flags first:

```bash
# Discover prompt flags (run these to see options)
codex --help | grep -i prompt
copilot --help | grep -i prompt
gemini --help | grep -i prompt
```

Common patterns:
```bash
# Codex - typically takes prompt as argument
codex "$PROMPT"

# Copilot - may use stdin or -m flag
echo "$PROMPT" | copilot

# Gemini - check for prompt flag
gemini --prompt "$PROMPT"
```

Send to each pane:
```bash
PROMPT="Create X in a single index.html file. Self-contained, no external deps."
WORKDIR="$CHALLENGES_DIR/$CHALLENGE_ID"

# Spawn in each pane
tmux send-keys -t $CODEX_PANE "cd $WORKDIR/codex && codex \"$PROMPT\"" Enter
tmux send-keys -t $COPILOT_PANE "cd $WORKDIR/copilot && copilot \"$PROMPT\"" Enter
tmux send-keys -t $GEMINI_PANE "cd $WORKDIR/gemini && gemini \"$PROMPT\"" Enter

# Conductor works in claude/ folder
cd $WORKDIR/claude
# ... do the work here
```

### Phase 5: Monitor & Collect

Watch all 4 panes. When each completes:

```bash
# Check for outputs
ls -la $WORKDIR/*/index.html

# When all done, anonymize
cd $WORKDIR
FILES=(claude/index.html codex/index.html copilot/index.html gemini/index.html)
LETTERS=(a b c d)

# Shuffle (using shuf or sort -R)
SHUFFLED=($(printf '%s\n' "${FILES[@]}" | shuf))

# Copy to anonymized names
for i in "${!SHUFFLED[@]}"; do
    cp "${SHUFFLED[$i]}" "${LETTERS[$i]}.html"
done

# Create meta.json with answers
# ...
```

### Phase 6: View Results

```bash
# Open gallery
cd ~/projects/model-arena
python -m http.server 8080
# Visit http://localhost:8080
```

## Tips

- Conductor (you) can work on the claude/ entry while watching others
- Some CLIs may need `--yes` or `-y` to skip confirmations
- If a model fails, you still have 3 others to compare
- The quad-split lets you watch all progress in real-time

## CLI Commands Reference

Each CLI takes a prompt and has auto-approve flags:

```bash
# Claude Code - positional prompt (bypass permissions via user config)
claude "$PROMPT"

# Codex - positional prompt, has exec subcommand for non-interactive
codex "$PROMPT"
# or non-interactive:
codex exec "$PROMPT"

# Gemini - positional query, -y/--yolo for auto-approve
gemini -y "$PROMPT"

# Copilot - use -i for interactive with prompt, -p for non-interactive
copilot -i "$PROMPT" --allow-all-tools
```

### Full Spawn Commands

```bash
PROMPT="Create a lava lamp effect in a single index.html file. Self-contained, inline CSS/JS, no external deps."
WORKDIR="$CHALLENGES_DIR/$CHALLENGE_ID"

# Codex pane
tmux send-keys -t $CODEX_PANE "cd $WORKDIR/codex && codex \"$PROMPT\"" Enter

# Copilot pane
tmux send-keys -t $COPILOT_PANE "cd $WORKDIR/copilot && copilot -i \"$PROMPT\" --allow-all-tools" Enter

# Gemini pane (yolo mode)
tmux send-keys -t $GEMINI_PANE "cd $WORKDIR/gemini && gemini -y \"$PROMPT\"" Enter

# Conductor (you) works in claude folder
cd $WORKDIR/claude
# Start working on your entry...
```

### Auto-Approve Flags Summary

| CLI | Auto-Approve | Notes |
|-----|--------------|-------|
| `claude` | (user config) | Set in `~/.claude/settings.json` |
| `codex` | (default interactive) | Use `exec` subcommand for non-interactive |
| `gemini` | `-y` or `--yolo` | Auto-approves all actions |
| `copilot` | `-i` + `--allow-all-tools` | `-i "prompt"` for interactive, `-p` for headless |
