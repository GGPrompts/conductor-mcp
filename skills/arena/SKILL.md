# Model Arena

Run a blind comparison challenge across multiple AI models in parallel.

## Usage

```
/arena                           # Interactive setup with prompts
/arena "custom prompt here"      # Skip to spawn with custom prompt
```

## Interactive Setup

When run without arguments, ask the user:

### 1. Prompt Complexity

```
What complexity level?
```

| Option | Description |
|--------|-------------|
| Simple | Basic animations, single elements (bouncing ball, color picker) |
| Medium | Small games, editors (snake, markdown preview, todo app) |
| Complex | Advanced effects, multi-component (metaballs, 3D, physics) |
| Custom | User provides their own prompt |

### 2. Pick a Prompt

Based on complexity, offer 3-4 options:

**Simple prompts:**
- "Create a bouncing ball animation with trail effect"
- "Build a color picker with hex/rgb display"
- "Make an animated gradient background"
- "Create a digital clock with flip animation"

**Medium prompts:**
- "Build a snake game with score and game over"
- "Create a markdown editor with live preview"
- "Make a todo app with local storage"
- "Build a typing speed test"

**Complex prompts:**
- "Create a lava lamp with metaball blobs that merge and separate"
- "Build a particle system with gravity and mouse interaction"
- "Make a 3D rotating cube with CSS transforms"
- "Create a piano keyboard with sound synthesis"

### 3. Execution Mode

```
How should the models run?
```

| Mode | Description |
|------|-------------|
| Interactive | Watch each model work in real-time (default) |
| Headless | Models run silently, collect results when done |

### 4. Confirm & Spawn

```
Ready to spawn arena?

Contestants: Claude, Codex, Gemini
Prompt: "Create a bouncing ball..."
Mode: Interactive

[Start Arena]
```

## Execution

### Setup Challenge Folder

```bash
ARENA_DIR=~/projects/model-arena
CHALLENGES_DIR=$ARENA_DIR/challenges

NEXT_NUM=$(($(ls -1 "$CHALLENGES_DIR" 2>/dev/null | wc -l) + 1))
CHALLENGE_ID=$(printf "%03d" $NEXT_NUM)-$SLUG

mkdir -p "$CHALLENGES_DIR/$CHALLENGE_ID"/{claude,codex,gemini}
```

### Split Current Pane into Quad

```bash
CURRENT=$(tmux display-message -p '#{pane_id}')
WORKDIR="$CHALLENGES_DIR/$CHALLENGE_ID"

# Split right (claude contestant)
tmux split-window -h -t $CURRENT -c "$WORKDIR/claude"
CLAUDE_PANE=$(tmux display-message -p '#{pane_id}')

# Split left side down (codex)
tmux select-pane -t $CURRENT
tmux split-window -v -t $CURRENT -c "$WORKDIR/codex"
CODEX_PANE=$(tmux display-message -p '#{pane_id}')

# Split right side down (gemini)
tmux select-pane -t $CLAUDE_PANE
tmux split-window -v -t $CLAUDE_PANE -c "$WORKDIR/gemini"
GEMINI_PANE=$(tmux display-message -p '#{pane_id}')

# Return focus to conductor
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

### Spawn Commands

**Interactive mode** (watch them work):
```bash
ARENA_RULES="Create this in a single index.html file. Self-contained, inline CSS/JS, no external dependencies."
FULL_PROMPT="$USER_PROMPT\n\n$ARENA_RULES"

tmux send-keys -t $CLAUDE_PANE "claude \"$FULL_PROMPT\"" Enter
tmux send-keys -t $CODEX_PANE "codex \"$FULL_PROMPT\"" Enter
tmux send-keys -t $GEMINI_PANE "gemini -i \"$FULL_PROMPT\" -y" Enter
```

**Headless mode** (run silently):
```bash
tmux send-keys -t $CLAUDE_PANE "claude -p \"$FULL_PROMPT\" > index.html && echo Done" Enter
tmux send-keys -t $CODEX_PANE "codex exec \"$FULL_PROMPT\"" Enter
tmux send-keys -t $GEMINI_PANE "gemini -y \"$FULL_PROMPT\"" Enter
```

## Monitor & Collect

Watch the panes. When all complete:

```bash
# Check for outputs
ls -la $WORKDIR/*/index.html

# Anonymize
cd $WORKDIR
FILES=(claude/index.html codex/index.html gemini/index.html)
MODELS=("claude" "codex" "gemini")
LETTERS=(a b c)

INDICES=(0 1 2)
SHUFFLED=($(shuf -e "${INDICES[@]}"))

declare -A ANSWERS
for i in 0 1 2; do
    src_idx=${SHUFFLED[$i]}
    cp "${FILES[$src_idx]}" "${LETTERS[$i]}.html"
    ANSWERS[${LETTERS[$i]}]="${MODELS[$src_idx]}"
done

# Create meta.json
cat > meta.json << EOF
{
  "id": "$CHALLENGE_ID",
  "title": "$TITLE",
  "date": "$(date +%Y-%m-%d)",
  "prompt": "$USER_PROMPT",
  "contestants": ["claude", "codex", "gemini"],
  "answers": {
    "a": "${ANSWERS[a]}",
    "b": "${ANSWERS[b]}",
    "c": "${ANSWERS[c]}"
  }
}
EOF
```

### Add to Viewer

Edit `~/projects/model-arena/index.html` and add the challenge ID to the registry:

```javascript
const challengeIds = [
  'NEW-CHALLENGE-ID',  // Add here
  '007-balatro-lava',
  // ...
];
```

## CLI Reference

| CLI | Interactive | Headless |
|-----|-------------|----------|
| claude | `claude "prompt"` | `claude -p "prompt"` |
| codex | `codex "prompt"` | `codex exec "prompt"` |
| gemini | `gemini -i "prompt" -y` | `gemini -y "prompt"` |

## Tips

- Interactive mode lets you watch the race unfold
- Headless is faster but less fun
- Gemini often finishes first
- Codex in reasoning mode takes longer but often better results
- Some prompts favor different models - try a few!
