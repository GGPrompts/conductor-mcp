# tmux API Reference for conductor-mcp

A comprehensive reference of tmux commands relevant to orchestration workflows.

## Legend

- ✅ **Implemented** - Currently used in conductor-mcp
- 🎯 **High Value** - Strong candidate for addition
- 💡 **Useful** - Could be valuable in specific scenarios
- ⬜ **Low Priority** - Unlikely to need

---

## Session Management

| Command | Status | Description |
|---------|--------|-------------|
| `new-session` | ✅ | Create new session |
| `kill-session` | ✅ | Kill session |
| `list-sessions` | ✅ | List all sessions |
| `rename-session` | 💡 | Rename a session |
| `has-session` | 💡 | Check if session exists (returns exit code) |
| `attach-session` | ⬜ | Attach to session (interactive) |
| `detach-client` | ⬜ | Detach from session |
| `switch-client` | ⬜ | Switch attached client to different session |
| `lock-session` | ⬜ | Lock session |

### Examples

```bash
# Create session with name and working directory
tmux new-session -d -s worker-BD-abc -c /path/to/worktree

# Check if session exists
tmux has-session -t worker-BD-abc && echo "exists"

# Kill session
tmux kill-session -t worker-BD-abc

# List sessions with format
tmux list-sessions -F "#{session_name}|#{session_created}|#{session_windows}"

# Rename session
tmux rename-session -t old-name new-name
```

---

## Window Management

| Command | Status | Description |
|---------|--------|-------------|
| `new-window` | 💡 | Create new window (tab) in session |
| `kill-window` | 💡 | Kill a window |
| `list-windows` | 💡 | List windows in session |
| `rename-window` | 💡 | Rename window |
| `select-window` | 💡 | Switch to window |
| `next-window` | ⬜ | Go to next window |
| `previous-window` | ⬜ | Go to previous window |
| `last-window` | ⬜ | Go to last active window |
| `move-window` | ⬜ | Move window to another session |
| `link-window` | ⬜ | Link window to another session |
| `unlink-window` | ⬜ | Unlink window |
| `swap-window` | ⬜ | Swap two windows |
| `find-window` | ⬜ | Search for window |
| `rotate-window` | ⬜ | Rotate panes in window |
| `resize-window` | ⬜ | Resize window |
| `respawn-window` | ⬜ | Respawn dead window |

### Examples

```bash
# Create new window with name
tmux new-window -t session:1 -n "worker-BD-abc"

# List windows
tmux list-windows -t session -F "#{window_index}:#{window_name}"

# Rename window
tmux rename-window -t session:0 "conductor"

# Select window by index
tmux select-window -t session:2
```

---

## Pane Management

| Command | Status | Description |
|---------|--------|-------------|
| `split-window` | ✅ | Split pane |
| `kill-pane` | ✅ | Kill pane |
| `list-panes` | ✅ | List panes |
| `select-pane` | ✅ | Focus pane |
| `select-layout` | ✅ | Apply layout (tiled, even-horizontal, etc.) |
| `resize-pane` | 💡 | Resize pane by cells or percentage |
| `swap-pane` | 💡 | Swap two panes |
| `break-pane` | 💡 | Break pane out to own window |
| `join-pane` | 💡 | Move pane to another window |
| `move-pane` | 💡 | Move pane to another window/session |
| `last-pane` | ⬜ | Go to last active pane |
| `next-layout` | ⬜ | Cycle through layouts |
| `previous-layout` | ⬜ | Previous layout |
| `display-panes` | 💡 | Show pane numbers overlay |
| `respawn-pane` | 💡 | Respawn dead pane with command |

### Layout Types

```
even-horizontal  - All panes same width, side by side
even-vertical    - All panes same height, stacked
main-horizontal  - One large pane on top, others below
main-vertical    - One large pane on left, others right
tiled            - All panes equal size in grid
```

### Examples

```bash
# Split horizontally (side by side)
tmux split-window -h -t %0

# Split vertically (stacked)
tmux split-window -v -t %0

# Split with specific size (percentage)
tmux split-window -h -p 30 -t %0

# Resize pane
tmux resize-pane -t %0 -x 80    # Set width to 80 cols
tmux resize-pane -t %0 -y 24    # Set height to 24 rows
tmux resize-pane -t %0 -Z       # Toggle zoom (fullscreen)

# Swap panes
tmux swap-pane -s %0 -t %1

# Break pane to new window
tmux break-pane -t %0 -n "isolated"

# Apply layout
tmux select-layout -t session:0 tiled

# List panes with detailed info
tmux list-panes -t session -F "#{pane_id}|#{pane_index}|#{pane_width}x#{pane_height}|#{pane_current_command}"
```

---

## Input/Output

| Command | Status | Description |
|---------|--------|-------------|
| `send-keys` | ✅ | Send keystrokes to pane |
| `capture-pane` | ✅ | Capture pane contents |
| `pipe-pane` | 🎯 | Stream pane output to command/file |
| `display-message` | ✅ | Display message / get tmux variables |
| `display-popup` | 🎯 | Show floating popup window |
| `copy-mode` | 💡 | Enter copy/scroll mode |
| `paste-buffer` | ⬜ | Paste from buffer |
| `set-buffer` | ⬜ | Set buffer contents |
| `show-buffer` | ⬜ | Show buffer contents |
| `list-buffers` | ⬜ | List paste buffers |
| `load-buffer` | ⬜ | Load file into buffer |
| `save-buffer` | ⬜ | Save buffer to file |
| `delete-buffer` | ⬜ | Delete buffer |
| `choose-buffer` | ⬜ | Interactive buffer selection |
| `send-prefix` | ⬜ | Send prefix key |

### send-keys Options

```bash
# Send literal text (-l prevents key interpretation)
tmux send-keys -t %0 -l "echo hello"

# Send special keys
tmux send-keys -t %0 Enter
tmux send-keys -t %0 C-c        # Ctrl+C
tmux send-keys -t %0 C-d        # Ctrl+D (EOF)
tmux send-keys -t %0 Escape
tmux send-keys -t %0 Tab
tmux send-keys -t %0 Up Down Left Right

# Send hex codes
tmux send-keys -t %0 -H 0x1b    # Escape

# Combined: type command and press enter
tmux send-keys -t %0 -l "npm test" && sleep 0.8 && tmux send-keys -t %0 Enter
```

### capture-pane Options

```bash
# Capture visible content
tmux capture-pane -t %0 -p

# Capture with scrollback (last 1000 lines)
tmux capture-pane -t %0 -p -S -1000

# Capture everything (all history)
tmux capture-pane -t %0 -p -S -

# Capture to file
tmux capture-pane -t %0 -p > output.txt

# Capture with escape sequences (colors)
tmux capture-pane -t %0 -p -e
```

### pipe-pane (Real-time streaming) 🎯

```bash
# Stream all output to file
tmux pipe-pane -t %0 "cat >> /tmp/pane-output.log"

# Stream to command (e.g., grep for patterns)
tmux pipe-pane -t %0 "grep --line-buffered 'Error' >> /tmp/errors.log"

# Stop piping
tmux pipe-pane -t %0

# Pipe to script for real-time processing
tmux pipe-pane -t %0 "/path/to/monitor.sh"
```

### display-popup 🎯

```bash
# Simple popup with command
tmux display-popup -E "echo 'Hello!'; sleep 2"

# Popup with size
tmux display-popup -w 60 -h 20 -E "htop"

# Popup at position
tmux display-popup -x 10 -y 5 -w 40 -h 10 -E "date"

# Popup with title
tmux display-popup -T "Status" -E "echo 'All workers running'"

# Close on any key (-E exits when command finishes)
tmux display-popup -E -E "echo 'Press any key'; read -n 1"
```

---

## Synchronization & Hooks

| Command | Status | Description |
|---------|--------|-------------|
| `wait-for` | 🎯 | Wait for/signal a channel |
| `set-hook` | 🎯 | Set hook to run on events |
| `show-hooks` | 💡 | Show current hooks |
| `run-shell` | 💡 | Run shell command |
| `if-shell` | 💡 | Conditional execution |
| `confirm-before` | ⬜ | Confirm before command |

### wait-for (Synchronization) 🎯

```bash
# In script: wait for signal
tmux wait-for done-BD-abc

# In worker: send signal when done
tmux wait-for -S done-BD-abc

# With timeout (bash)
timeout 60 tmux wait-for done-BD-abc || echo "timed out"
```

### set-hook (Event triggers) 🎯

```bash
# Run command when pane dies
tmux set-hook -g pane-died "run-shell 'notify-send Pane died'"

# Run command when window created
tmux set-hook -g window-linked "run-shell 'echo window created'"

# Run command after pane content changes
tmux set-hook -g pane-set-clipboard "run-shell 'echo clipboard updated'"

# Session-specific hook
tmux set-hook -t session pane-exited "run-shell 'cleanup.sh'"

# Remove hook
tmux set-hook -gu pane-died
```

### Available Hook Events

```
after-bind-key           after-capture-pane       after-copy-mode
after-display-message    after-display-panes      after-kill-pane
after-list-buffers       after-list-clients       after-list-keys
after-list-panes         after-list-sessions      after-list-windows
after-load-buffer        after-lock-server        after-new-session
after-new-window         after-paste-buffer       after-pipe-pane
after-queue              after-refresh-client     after-rename-session
after-rename-window      after-resize-pane        after-resize-window
after-save-buffer        after-select-layout      after-select-pane
after-select-window      after-send-keys          after-set-buffer
after-set-environment    after-set-hook           after-set-option
after-set-window-option  after-show-environment   after-show-messages
after-show-options       after-show-window-options after-split-window
after-unbind-key         alert-activity           alert-bell
alert-silence            client-active            client-attached
client-detached          client-focus-in          client-focus-out
client-resized           client-session-changed   pane-died
pane-exited             pane-focus-in            pane-focus-out
pane-mode-changed       pane-set-clipboard       session-closed
session-created         session-renamed          session-window-changed
window-layout-changed   window-linked            window-pane-changed
window-renamed          window-unlinked
```

### run-shell

```bash
# Run command and display output
tmux run-shell "date"

# Run in background
tmux run-shell -b "sleep 10 && notify-send 'Done'"

# Run in specific pane's context
tmux run-shell -t %0 "pwd"
```

---

## Configuration & Options

| Command | Status | Description |
|---------|--------|-------------|
| `set-option` | 💡 | Set server/session/window option |
| `show-options` | 💡 | Show options |
| `set-window-option` | ⬜ | Set window option |
| `show-window-options` | ⬜ | Show window options |
| `set-environment` | 💡 | Set environment variable |
| `show-environment` | 💡 | Show environment |
| `source-file` | ⬜ | Load config file |

### Useful Options

```bash
# Allow mouse
tmux set-option -g mouse on

# Set base index
tmux set-option -g base-index 1

# Increase history
tmux set-option -g history-limit 50000

# Pane border status (show pane title)
tmux set-option -g pane-border-status top
tmux set-option -g pane-border-format "#{pane_index}: #{pane_title}"

# Set pane title
tmux select-pane -t %0 -T "Worker BD-abc"

# Automatic window renaming
tmux set-window-option -g automatic-rename on

# Set environment for session
tmux set-environment -t session BEADS_WORKING_DIR /path/to/project
```

---

## Format Variables

Use with `-F` flag in list commands.

### Session Variables
```
#{session_name}          Session name
#{session_id}            Session ID ($0, $1, etc.)
#{session_created}       Creation time (Unix timestamp)
#{session_windows}       Number of windows
#{session_attached}      1 if attached, 0 if not
#{session_activity}      Last activity time
#{session_path}          Working directory
```

### Window Variables
```
#{window_index}          Window index
#{window_name}           Window name
#{window_active}         1 if active window
#{window_panes}          Number of panes
#{window_layout}         Current layout
#{window_width}          Width in cells
#{window_height}         Height in cells
```

### Pane Variables
```
#{pane_id}               Pane ID (%0, %1, etc.)
#{pane_index}            Pane index in window
#{pane_active}           1 if active pane
#{pane_width}            Width in cells
#{pane_height}           Height in cells
#{pane_current_command}  Current command
#{pane_current_path}     Current directory
#{pane_pid}              PID of command
#{pane_title}            Pane title
#{pane_tty}              TTY device
#{pane_dead}             1 if pane is dead
#{pane_in_mode}          1 if in copy mode
#{scroll_position}       Scroll position in copy mode
```

### Example Format Strings

```bash
# List sessions with custom format
tmux list-sessions -F "#{session_name}: #{session_windows} windows, created #{session_created}"

# List panes with full info
tmux list-panes -F "#{pane_id} | #{pane_index} | #{pane_width}x#{pane_height} | #{pane_current_command} | #{pane_current_path}"

# Check if pane is running specific command
tmux list-panes -F "#{pane_id}:#{pane_current_command}" | grep claude
```

---

## Recommended Additions to conductor-mcp

### Priority 1: Real-time Monitoring

```python
@mcp.tool()
def watch_pane(pane_id: str, output_file: str = "/tmp/pane-watch.log") -> str:
    """Stream pane output to file for real-time monitoring."""
    subprocess.run(["tmux", "pipe-pane", "-t", pane_id, f"cat >> {output_file}"])
    return f"Watching {pane_id} -> {output_file}"

@mcp.tool()
def stop_watch(pane_id: str) -> str:
    """Stop streaming pane output."""
    subprocess.run(["tmux", "pipe-pane", "-t", pane_id])
    return f"Stopped watching {pane_id}"
```

### Priority 2: Synchronization

```python
@mcp.tool()
async def wait_for_signal(channel: str, timeout_s: int = 300) -> str:
    """Wait for worker to signal completion."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tmux", "wait-for", channel,
            stdout=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        return f"Received signal: {channel}"
    except asyncio.TimeoutError:
        proc.kill()
        return f"Timeout waiting for: {channel}"

@mcp.tool()
def send_signal(channel: str) -> str:
    """Send signal (worker calls this when done)."""
    subprocess.run(["tmux", "wait-for", "-S", channel])
    return f"Sent signal: {channel}"
```

### Priority 3: Popups

```python
@mcp.tool()
def show_popup(
    message: str,
    title: str = "Conductor",
    width: int = 50,
    height: int = 10,
    wait: bool = True
) -> str:
    """Show floating popup notification."""
    cmd = ["tmux", "display-popup", "-T", title, "-w", str(width), "-h", str(height)]
    if wait:
        cmd.extend(["-E", f"echo '{message}'; echo; echo 'Press any key...'; read -n 1"])
    else:
        cmd.extend(["-E", f"echo '{message}'; sleep 3"])
    subprocess.run(cmd)
    return f"Displayed popup: {message[:30]}..."
```

### Priority 4: Hooks

```python
@mcp.tool()
def on_pane_exit(callback_script: str) -> str:
    """Run script when any pane exits."""
    subprocess.run(["tmux", "set-hook", "-g", "pane-exited", f"run-shell '{callback_script}'"])
    return f"Hook set: pane-exited -> {callback_script}"

@mcp.tool()
def clear_hooks() -> str:
    """Clear all custom hooks."""
    for hook in ["pane-exited", "pane-died", "window-linked"]:
        subprocess.run(["tmux", "set-hook", "-gu", hook], capture_output=True)
    return "Hooks cleared"
```

---

## Quick Reference Card

```
SESSION:    new-session -d -s name -c dir
            kill-session -t name
            list-sessions -F format
            has-session -t name

WINDOW:     new-window -t sess:idx -n name
            kill-window -t sess:idx
            list-windows -t sess -F format
            rename-window -t sess:idx name

PANE:       split-window -h|-v -t pane
            kill-pane -t pane
            list-panes -t sess -F format
            select-pane -t pane
            resize-pane -t pane -x W -y H -Z
            select-layout tiled|even-horizontal|even-vertical

I/O:        send-keys -t pane -l "text"
            send-keys -t pane Enter|C-c|Escape
            capture-pane -t pane -p -S -1000
            pipe-pane -t pane "cmd"
            display-popup -T title -w W -h H -E "cmd"

SYNC:       wait-for channel      # wait for signal
            wait-for -S channel   # send signal

HOOKS:      set-hook -g event "run-shell 'cmd'"
            show-hooks -g
            set-hook -gu event    # remove hook
```
