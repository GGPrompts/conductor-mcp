# Common Conductor Workflows

> Prefer `cm` via Bash for everything except the spawn/signal primitives. Every `cm` verb accepts `--json` for structured output.

## 1. Spawn a Wave of Workers

Spawn workers for all ready beads issues, visible in the current session:

```
1. bd ready                          # Find ready issues (Bash)
2. smart_spawn_wave(                 # Spawn all at once (MCP primitive)
     issue_ids="BD-abc,BD-def",
     project_dir="/path/to/project"
   )
3. cm speak "Wave started"          # Announce (CLI)
```

Workers auto-split panes, overflowing to new tabs when needed.

## 2. Spawn with a Specific Profile

Use codex, gemini, tfe, or any configured tool instead of claude:

```
smart_spawn(
  issue_id="BD-abc",
  project_dir="/path/to/project",
  profile="codex"                    # Uses "codex" command from profiles
)
```

Or with a raw command:
```
smart_spawn(
  issue_id="BD-abc",
  project_dir="/path/to/project",
  profile_cmd="gemini -i --model=2.5-pro"
)
```

## 3. Monitor Workers

Check all workers and their context usage:

```
cm list workers                    # Get active sessions (TSV)
cm context BD-abc                  # Check context per worker
cm worker capacity --threshold 60  # Find workers that can take more work
cm capture BD-abc --lines 50       # See what a worker is doing
```

For continuous monitoring:
```
cm watch start %5                  # Start streaming output
cm watch read %5 --lines 20        # Check periodically
cm watch stop %5                   # Stop when done
```

## 4. Reuse Workers with Capacity

Instead of spawning new workers, reuse ones with remaining context:

```
cm worker capacity --threshold 60  # Find workers below 60% context
cm send BD-abc "Now work on BD-def: ..."  # Send new task to existing worker
```

## 5. Kill All Workers

Clean shutdown of all workers:

```
cm list workers                    # See what's running
cm kill worker BD-abc              # Kill each session
cm kill worker BD-def \
  --cleanup-worktree \
  --project-dir /path/to/project   # Kill + clean worktree
```

Voice-assignment reset lives in the conductor-tui Settings panel (cm-3gw).

## 6. Custom Grid Layout

For manual control over worker placement:

```
cm grid 2x2                        # Create 4 panes (CLI)
cm spawn in-pane %5 BD-abc \
  --project-dir /path/to/project   # Populate each pane
```
