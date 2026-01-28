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
mkdir -p "$CHALLENGES_DIR/$CHALLENGE_ID"/{claude,codex,gemini}
```

### Phase 3: Split Current Pane into Quad

Split your current pane into 4 (you stay in top-left):

```bash
# Get current pane
CURRENT=$(tmux display-message -p '#{pane_id}')

# Split right (creates pane for claude contestant)
tmux split-window -h -t $CURRENT -c "$WORKDIR/claude"
CLAUDE_PANE=$(tmux display-message -p '#{pane_id}')

# Split the left side down (creates pane for codex)
tmux select-pane -t $CURRENT
tmux split-window -v -t $CURRENT -c "$WORKDIR/codex"
CODEX_PANE=$(tmux display-message -p '#{pane_id}')

# Split the right side down (creates pane for gemini)
tmux select-pane -t $CLAUDE_PANE
tmux split-window -v -t $CLAUDE_PANE -c "$WORKDIR/gemini"
GEMINI_PANE=$(tmux display-message -p '#{pane_id}')

# Return focus to conductor pane
tmux select-pane -t $CURRENT
```

Result:
```
┌──────────────┬──────────────┐
│  Conductor   │   Claude     │
│  (watching)  │  (competing) │
├──────────────┼──────────────┤
│    Codex     │   Gemini     │
│  (competing) │  (competing) │
└──────────────┴──────────────┘
```

### Phase 4: Spawn Models with Prompts

Each CLI needs its prompt passed correctly. Check flags first:

```bash
# Discover prompt flags (run these to see options)
claude --help | grep -i prompt
codex --help | grep -i prompt
gemini --help | grep -i prompt
```

Common patterns:
```bash
# Claude - positional prompt
claude "$PROMPT"

# Codex - positional prompt
codex "$PROMPT"

# Gemini - positional with -y for auto-approve
gemini -y "$PROMPT"
```

Send to each pane:
```bash
PROMPT="Create X in a single index.html file. Self-contained, no external deps."
WORKDIR="$CHALLENGES_DIR/$CHALLENGE_ID"

# Spawn all 3 contestants
tmux send-keys -t $CLAUDE_PANE "claude \"$PROMPT\"" Enter
tmux send-keys -t $CODEX_PANE "codex \"$PROMPT\"" Enter
tmux send-keys -t $GEMINI_PANE "gemini -y \"$PROMPT\"" Enter

# Conductor stays in current pane and watches
```

### Phase 5: Monitor & Collect

Watch all 3 panes. When each completes:

```bash
# Check for outputs
ls -la $WORKDIR/*/index.html

# When all done, anonymize
cd $WORKDIR
FILES=(claude/index.html codex/index.html gemini/index.html)
LETTERS=(a b c)

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

- Conductor watches all 3 compete - you don't participate
- Some CLIs may need `--yes` or `-y` to skip confirmations
- If a model fails, you still have 2 others to compare
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
```

### Full Spawn Commands

```bash
PROMPT="Create a lava lamp effect in a single index.html file. Self-contained, inline CSS/JS, no external deps."
WORKDIR="$CHALLENGES_DIR/$CHALLENGE_ID"

# Claude pane
tmux send-keys -t $CLAUDE_PANE "claude \"$PROMPT\"" Enter

# Codex pane
tmux send-keys -t $CODEX_PANE "codex \"$PROMPT\"" Enter

# Gemini pane (yolo mode)
tmux send-keys -t $GEMINI_PANE "gemini -y \"$PROMPT\"" Enter

# Conductor watches from current pane
```

### Auto-Approve Flags Summary

| CLI | Auto-Approve | Notes |
|-----|--------------|-------|
| `claude` | (user config) | Set in `~/.claude/settings.json` |
| `codex` | (default interactive) | Use `exec` subcommand for non-interactive |
| `gemini` | `-y` or `--yolo` | Auto-approves all actions |
