# Common Conductor Workflows

## 1. Spawn a Wave of Workers

Spawn workers for all ready beads issues, visible in the current session:

```
1. bd ready                          # Find ready issues
2. smart_spawn_wave(                 # Spawn all at once
     issue_ids="BD-abc,BD-def",
     project_dir="/path/to/project"
   )
3. speak("Wave started")            # Announce
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
1. list_workers()                    # Get active sessions
2. get_context_percent("BD-abc")     # Check context per worker
3. get_workers_with_capacity(60)     # Find workers that can take more work
4. capture_worker_output("BD-abc")   # See what a worker is doing
```

For continuous monitoring:
```
1. watch_pane("%5")                  # Start streaming output
2. read_watch("%5", lines=20)        # Check periodically
3. stop_watch("%5")                  # Stop when done
```

## 4. Reuse Workers with Capacity

Instead of spawning new workers, reuse ones with remaining context:

```
1. get_workers_with_capacity(60)     # Find workers below 60% context
2. send_keys("BD-abc",              # Send new task to existing worker
     "Now work on BD-def: ...")
```

## 5. Kill All Workers

Clean shutdown of all workers:

```
1. list_workers()                    # See what's running
2. kill_worker("BD-abc")             # Kill each session
3. kill_worker("BD-def",             # Kill + clean worktree
     cleanup_worktree=True,
     project_dir="/path/to/project")
4. reset_voice_assignments()         # Free voice pool
```

## 6. Custom Grid Layout

For manual control over worker placement:

```
1. create_grid(layout="2x2")        # Create 4 panes
2. spawn_worker_in_pane(             # Populate each pane
     pane_id="%5",
     issue_id="BD-abc",
     project_dir="/path/to/project"
   )
```
