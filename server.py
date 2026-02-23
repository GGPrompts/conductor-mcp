#!/usr/bin/env python3
"""
conductor-mcp: Terminal-only orchestration MCP server

Brings TabzChrome's orchestration superpowers to any terminal.
"""

import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("conductor")

# Configuration
STATE_DIR = Path("/tmp/claude-code-state")
AUDIO_CACHE_DIR = Path("/tmp/conductor-audio-cache")
CONFIG_DIR = Path.home() / ".config" / "conductor-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Defaults (used in function signatures)
DEFAULT_DELAY_MS = 800

# Ensure directories exist
STATE_DIR.mkdir(exist_ok=True)
AUDIO_CACHE_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Available edge-tts voices (good variety for distinguishing workers)
VOICE_POOL = [
    "en-US-AriaNeural",      # Female, conversational
    "en-US-GuyNeural",       # Male, conversational
    "en-US-JennyNeural",     # Female, assistant
    "en-US-DavisNeural",     # Male, calm
    "en-US-AmberNeural",     # Female, warm
    "en-US-AndrewNeural",    # Male, confident
    "en-US-EmmaNeural",      # Female, friendly
    "en-US-BrianNeural",     # Male, professional
    "en-US-AnaNeural",       # Female, child-like
    "en-US-ChristopherNeural", # Male, reliable
    "en-GB-SoniaNeural",     # British female
    "en-GB-RyanNeural",      # British male
    "en-AU-NatashaNeural",   # Australian female
    "en-AU-WilliamNeural",   # Australian male
]

# Default configuration
DEFAULT_CONFIG = {
    "max_concurrent_workers": 4,
    "default_layout": "2x2",
    "min_pane_width": 80,
    "min_pane_height": 24,
    "conductor_mode": "session",  # future: "sidebar" | "popup"
    "voice": {
        "default": "en-US-AndrewNeural",  # Conductor's authoritative voice
        "rate": "+20%",
        "pitch": "+0Hz",
        "random_per_worker": True,
    },
    "delays": {
        "send_keys_ms": 800,
        "claude_boot_s": 4,
    },
    "worker_voice_assignments": {},  # worker_id -> voice
    "voice_pool_index": 0,  # Tracks which voice to assign next
}


def load_config() -> dict:
    """Load config from file, creating default if needed."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_worker_voice(worker_id: str) -> str:
    """Get or assign a unique voice for a worker."""
    config = load_config()

    if not config["voice"]["random_per_worker"]:
        return config["voice"]["default"]

    assignments = config.get("worker_voice_assignments", {})

    # Already assigned?
    if worker_id in assignments:
        return assignments[worker_id]

    # Find next unused voice
    used_voices = set(assignments.values())
    pool_index = config.get("voice_pool_index", 0)

    # Try to find an unused voice, cycling through pool
    for i in range(len(VOICE_POOL)):
        voice = VOICE_POOL[(pool_index + i) % len(VOICE_POOL)]
        if voice not in used_voices:
            assignments[worker_id] = voice
            config["worker_voice_assignments"] = assignments
            config["voice_pool_index"] = (pool_index + i + 1) % len(VOICE_POOL)
            save_config(config)
            return voice

    # All voices used, cycle through anyway
    voice = VOICE_POOL[pool_index % len(VOICE_POOL)]
    assignments[worker_id] = voice
    config["worker_voice_assignments"] = assignments
    config["voice_pool_index"] = (pool_index + 1) % len(VOICE_POOL)
    save_config(config)
    return voice


def release_worker_voice(worker_id: str) -> None:
    """Release a worker's voice assignment when killed."""
    config = load_config()
    assignments = config.get("worker_voice_assignments", {})
    if worker_id in assignments:
        del assignments[worker_id]
        config["worker_voice_assignments"] = assignments
        save_config(config)


def _find_best_split(
    session: str,
    min_w: int,
    min_h: int,
    target_pane: Optional[str] = None
) -> dict:
    """
    Decide where to place a new worker pane.

    Evaluates panes in the session and returns the best split action.
    Prefers horizontal splits (side-by-side), falls back to vertical,
    then new window if no pane can be split.

    Returns:
        {"action": "split_h"|"split_v"|"new_window", "target_pane": ..., "reason": ...}
    """
    panes = list_panes(session)
    if not panes:
        return {
            "action": "new_window",
            "target_pane": None,
            "reason": "No panes found in session"
        }

    # If target_pane specified, only evaluate that one
    if target_pane:
        candidates = [p for p in panes if p["pane_id"] == target_pane]
        if not candidates:
            return {
                "action": "new_window",
                "target_pane": None,
                "reason": f"Target pane {target_pane} not found"
            }
    else:
        # Sort by area, largest first
        candidates = sorted(panes, key=lambda p: p["width"] * p["height"], reverse=True)

    for pane in candidates:
        w, h = pane["width"], pane["height"]

        # Check horizontal split (side-by-side): each half gets ~w/2
        half_w = w // 2
        if half_w >= min_w and h >= min_h:
            return {
                "action": "split_h",
                "target_pane": pane["pane_id"],
                "reason": f"Horizontal split of {pane['pane_id']} ({w}x{h}) -> 2x({half_w}x{h})"
            }

        # Check vertical split (stacked): each half gets ~h/2
        half_h = h // 2
        if w >= min_w and half_h >= min_h:
            return {
                "action": "split_v",
                "target_pane": pane["pane_id"],
                "reason": f"Vertical split of {pane['pane_id']} ({w}x{h}) -> 2x({w}x{half_h})"
            }

    return {
        "action": "new_window",
        "target_pane": None,
        "reason": f"No pane large enough to split (need {min_w}x{min_h} per half)"
    }


@mcp.tool()
async def send_keys(
    session: str,
    keys: str,
    submit: bool = True,
    delay_ms: int = DEFAULT_DELAY_MS
) -> str:
    """
    Send keys to a tmux session. If submit=True, waits then presses Enter.

    The delay between sending text and pressing Enter is critical for Claude/Codex -
    without it, they create a newline instead of submitting the prompt.

    Args:
        session: tmux session name (e.g., "BD-abc" or "ctt-profile-uuid")
        keys: The text/keys to send
        submit: If True, wait delay_ms then press Enter (default: True)
        delay_ms: Milliseconds to wait before Enter (default: 800, ignored if submit=False)

    Returns:
        Confirmation message
    """
    # Send the keys (literal mode to avoid tmux interpretation)
    subprocess.run(
        ["tmux", "send-keys", "-t", session, "-l", keys],
        check=True
    )

    if submit:
        # Wait for input detection
        await asyncio.sleep(delay_ms / 1000)

        # Press Enter to submit
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            check=True
        )
        return f"Sent keys to {session} ({len(keys)} chars, submitted after {delay_ms}ms)"

    return f"Sent keys to {session} ({len(keys)} chars, no submit)"


@mcp.tool()
async def spawn_worker(
    issue_id: str,
    project_dir: str,
    profile_cmd: str = "claude",
    inject_context: bool = True
) -> dict:
    """
    Spawn a worker: create worktree, tmux session, and optionally inject beads context.

    Args:
        issue_id: Beads issue ID (e.g., "BD-abc")
        project_dir: Path to the main project directory
        profile_cmd: Command to run (default: "claude")
        inject_context: Whether to inject beads context (default: True)

    Returns:
        Dict with session info
    """
    project_path = Path(project_dir).expanduser().resolve()
    worktree_path = project_path / ".worktrees" / issue_id
    branch_name = f"feature/{issue_id}"

    # 1. Create worktree if it doesn't exist
    if not worktree_path.exists():
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if branch exists
        result = subprocess.run(
            ["git", "-C", str(project_path), "branch", "--list", branch_name],
            capture_output=True, text=True
        )

        if result.stdout.strip():
            # Branch exists, use it
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 str(worktree_path), branch_name],
                check=True
            )
        else:
            # Create new branch
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 "-b", branch_name, str(worktree_path)],
                check=True
            )

    # 2. Create tmux session
    session_name = issue_id
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name,
         "-c", str(worktree_path)],
        check=False  # May fail if session exists
    )

    # 3. Launch Claude/Codex
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, profile_cmd, "Enter"],
        check=True
    )

    # 4. Wait for Claude to boot
    await asyncio.sleep(4)

    # 5. Inject context if requested
    context_text = ""
    if inject_context:
        try:
            # Get issue details from beads
            result = subprocess.run(
                ["bd", "show", issue_id, "--format", "json"],
                capture_output=True, text=True,
                cwd=str(project_path),
                env={**os.environ, "BEADS_WORKING_DIR": str(project_path)}
            )
            if result.returncode == 0:
                issue = json.loads(result.stdout)
                context_text = f"""Fix beads issue {issue_id}: "{issue.get('title', 'Unknown')}"

{issue.get('description', '')}

When done:
1. Run tests/build to verify
2. Commit your changes
3. Run: bd close {issue_id} --reason "Brief description of fix"
"""
        except Exception as e:
            context_text = f"Work on issue {issue_id}. When done: bd close {issue_id}"

    # 6. Send the keys
    if context_text:
        await send_keys(session_name, context_text)

    return {
        "session": session_name,
        "worktree": str(worktree_path),
        "branch": branch_name,
        "context_injected": bool(context_text)
    }


# Audio mutex - shared with audio-announcer.sh hooks
AUDIO_LOCK_FILE = Path("/tmp/claude-audio.lock")


@mcp.tool()
async def speak(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    worker_id: Optional[str] = None,
    blocking: bool = False,
    priority: bool = True
) -> str:
    """
    Speak text aloud using edge-tts.

    Args:
        text: Text to speak
        voice: Edge TTS voice (default from config, or worker's assigned voice)
        rate: Speech rate (e.g., "+0%", "+20%", "-10%")
        worker_id: If provided, uses this worker's unique assigned voice
        blocking: Wait for speech to complete (default: False)
        priority: Wait for audio lock (default: True). Direct calls take priority over hooks.

    Returns:
        Confirmation message
    """
    import fcntl

    config = load_config()

    # Determine voice
    if voice is None:
        if worker_id:
            voice = get_worker_voice(worker_id)
        else:
            voice = config["voice"]["default"]

    # Determine rate
    if rate is None:
        rate = config["voice"]["rate"]

    # Generate cache key
    cache_key = hashlib.md5(f"{voice}:{rate}:{text}".encode()).hexdigest()
    cache_file = AUDIO_CACHE_DIR / f"{cache_key}.mp3"

    # Generate audio if not cached
    if not cache_file.exists():
        try:
            # Use edge-tts CLI
            subprocess.run(
                ["edge-tts", "--voice", voice, "--rate", rate,
                 "--text", text, "--write-media", str(cache_file)],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            return f"TTS generation failed: {e.stderr.decode() if e.stderr else str(e)}"
        except FileNotFoundError:
            return "edge-tts not found. Install with: pip install edge-tts"

    # Acquire audio lock (priority=True waits, False skips if busy)
    lock_fd = None
    try:
        lock_fd = open(AUDIO_LOCK_FILE, 'w')
        if priority:
            # Wait up to 5 seconds for lock - direct calls take priority
            for _ in range(50):
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.1)
            else:
                # Couldn't get lock, proceed anyway for priority calls
                pass
        else:
            # Non-blocking - skip if busy
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "Audio busy, skipped"

        # Try multiple audio players in order of preference
        players = [
            (["mpv", "--no-video", "--really-quiet", str(cache_file)], "mpv"),
            (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(cache_file)], "ffplay"),
            (["cvlc", "--play-and-exit", "--quiet", str(cache_file)], "vlc"),
        ]

        played = False
        for cmd, name in players:
            try:
                if blocking or priority:
                    # Priority calls block to hold lock during playback
                    subprocess.run(cmd, check=True, capture_output=True)
                else:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                played = True
                break
            except FileNotFoundError:
                continue

        if not played:
            return f"Audio cached at {cache_file} - install mpv, ffplay, or vlc to play"

    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except:
                pass

    return f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}"


@mcp.tool()
def kill_worker(
    session: str,
    cleanup_worktree: bool = False,
    project_dir: Optional[str] = None
) -> str:
    """
    Kill a worker's tmux session and optionally clean up the worktree.

    Args:
        session: tmux session name (usually the issue_id like "BD-abc")
        cleanup_worktree: Also remove the git worktree (default: False)
        project_dir: Project directory (required if cleanup_worktree=True)

    Returns:
        Confirmation message
    """
    # Kill tmux session
    result = subprocess.run(
        ["tmux", "kill-session", "-t", session],
        capture_output=True, text=True
    )

    messages = []
    if result.returncode == 0:
        messages.append(f"Killed session: {session}")
    else:
        messages.append(f"Session {session} not found or already killed")

    # Clean up state file
    state_file = STATE_DIR / f"{session}.json"
    if state_file.exists():
        state_file.unlink()
        messages.append("Removed state file")

    # Release voice assignment
    release_worker_voice(session)

    # Clean up worktree if requested
    if cleanup_worktree:
        if not project_dir:
            messages.append("Warning: project_dir required for worktree cleanup")
        else:
            project_path = Path(project_dir).expanduser().resolve()
            worktree_path = project_path / ".worktrees" / session

            if worktree_path.exists():
                result = subprocess.run(
                    ["git", "-C", str(project_path), "worktree", "remove",
                     str(worktree_path), "--force"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    messages.append(f"Removed worktree: {worktree_path}")
                else:
                    messages.append(f"Failed to remove worktree: {result.stderr.strip()}")
            else:
                messages.append(f"Worktree not found: {worktree_path}")

    return "; ".join(messages)


@mcp.tool()
def list_workers() -> list[dict]:
    """
    List active tmux sessions that look like workers.

    Returns:
        List of worker session info
    """
    result = subprocess.run(
        ["tmux", "list-sessions", "-F",
         "#{session_name}|#{session_created}|#{session_windows}|#{session_attached}"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return []

    workers = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            name = parts[0]
            # Get status from state file if available
            status = None
            state_file = STATE_DIR / f"{name}.json"
            if state_file.exists():
                try:
                    with open(state_file) as f:
                        state = json.load(f)
                        status = state.get("status")
                except (json.JSONDecodeError, IOError):
                    pass  # State file corrupt or unreadable, continue without status

            workers.append({
                "session": name,
                "created": parts[1],
                "windows": int(parts[2]),
                "attached": parts[3] == "1",
                "claude_status": status
            })

    return workers


@mcp.tool()
def get_worker_status(session: str) -> Optional[dict]:
    """
    Get Claude's current status for a worker session.

    Reads from /tmp/claude-code-state/{session}.json written by Claude hooks.

    Args:
        session: tmux session name

    Returns:
        Status dict or None if not found
    """
    state_file = STATE_DIR / f"{session}.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _get_context_from_state_files(target: str) -> dict | None:
    """
    Try to get context percentage from state files written by the statusline script.

    Returns None if data unavailable or stale (>30 seconds old).
    """
    import time

    # First, get the pane ID for this target
    result = subprocess.run(
        ["tmux", "display-message", "-t", target, "-p", "#{pane_id}"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return None

    pane_id = result.stdout.strip()
    # Sanitize pane ID same way as state-tracker.sh
    sanitized_pane_id = pane_id.replace("%", "_").replace(":", "_")

    state_file = STATE_DIR / f"{sanitized_pane_id}.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            state = json.load(f)

        # Get the claude_session_id that links to the context file
        claude_session_id = state.get("claude_session_id")
        if not claude_session_id:
            return None

        # Read the context file
        context_file = STATE_DIR / f"{claude_session_id}-context.json"
        if not context_file.exists():
            return None

        # Check if context file is fresh (within 30 seconds)
        file_age = time.time() - context_file.stat().st_mtime
        if file_age > 30:
            return None

        with open(context_file) as f:
            context_data = json.load(f)

        context_pct = context_data.get("context_pct")
        if context_pct is None:
            return None

        # Extract additional token info if available
        context_window = context_data.get("context_window", {})

        return {
            "target": target,
            "context_percent": int(context_pct),
            "source": "state_file",
            "status": "ok",
            "context_window_size": context_window.get("context_window_size"),
            "total_input_tokens": context_window.get("total_input_tokens"),
            "total_output_tokens": context_window.get("total_output_tokens"),
            "file_age_seconds": round(file_age, 1)
        }
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def _get_context_from_terminal(target: str) -> dict:
    """
    Fallback: scrape context percentage from terminal status line.
    """
    import re

    # Capture the last few lines to find the status line
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p", "-S", "-5"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return {
            "error": f"Failed to capture pane: {result.stderr.strip()}",
            "context_percent": None
        }

    lines = result.stdout.strip().split("\n")

    # Look for the status line pattern with "% ctx"
    pattern = r"(\d+)%\s*ctx"

    for line in reversed(lines):  # Start from bottom
        match = re.search(pattern, line)
        if match:
            percent = int(match.group(1))
            return {
                "target": target,
                "context_percent": percent,
                "source": "terminal_scrape",
                "raw_line": line.strip(),
                "status": "ok"
            }

    return {
        "target": target,
        "context_percent": None,
        "source": "terminal_scrape",
        "raw_line": lines[-1] if lines else "",
        "status": "not_found",
        "hint": "Status line not visible - Claude may be processing or pane too small"
    }


@mcp.tool()
def get_context_percent(target: str) -> dict:
    """
    Get the context usage percentage from a Claude Code session.

    Attempts to read from state files first (accurate, from statusline script),
    then falls back to parsing the visible terminal status line.

    Args:
        target: tmux session name or pane ID (e.g., "BD-abc" or "%5")

    Returns:
        Dict with context_percent (int 0-100), source ("state_file" or "terminal_scrape"),
        and additional token info when available from state files.
    """
    # Try state files first (more accurate)
    result = _get_context_from_state_files(target)
    if result is not None:
        return result

    # Fall back to terminal scraping
    return _get_context_from_terminal(target)


@mcp.tool()
def get_workers_with_capacity(threshold: int = 60) -> dict:
    """
    Find workers that have remaining context capacity for more tasks.

    Checks all active workers and returns those below the context threshold.
    Useful for deciding whether to reuse existing workers vs spawn new ones.

    Args:
        threshold: Context % below which a worker has capacity (default: 60)

    Returns:
        Dict with workers_with_capacity list and summary stats
    """
    workers = list_workers()

    if not workers:
        return {
            "workers_with_capacity": [],
            "workers_at_capacity": [],
            "total_workers": 0,
            "available_capacity": 0
        }

    with_capacity = []
    at_capacity = []

    for w in workers:
        session = w["session"]
        ctx_info = get_context_percent(session)

        worker_info = {
            "session": session,
            "context_percent": ctx_info.get("context_percent"),
            "claude_status": w.get("claude_status"),
            "attached": w.get("attached", False)
        }

        if ctx_info.get("context_percent") is not None:
            if ctx_info["context_percent"] < threshold:
                worker_info["remaining_capacity"] = threshold - ctx_info["context_percent"]
                with_capacity.append(worker_info)
            else:
                at_capacity.append(worker_info)
        else:
            # Can't determine context, assume at capacity to be safe
            at_capacity.append(worker_info)

    return {
        "workers_with_capacity": sorted(with_capacity, key=lambda x: x.get("context_percent", 100)),
        "workers_at_capacity": at_capacity,
        "total_workers": len(workers),
        "available_for_tasks": len(with_capacity),
        "threshold": threshold
    }


@mcp.tool()
def capture_worker_output(session: str, lines: int = 50) -> str:
    """
    Capture recent output from a worker's tmux pane.

    Args:
        session: tmux session name
        lines: Number of lines to capture (default: 50)

    Returns:
        Captured terminal output
    """
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to capture: {result.stderr}"

    return result.stdout


# ═══════════════════════════════════════════════════════════════
# SESSION & WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def create_session(
    name: str,
    start_dir: Optional[str] = None,
    command: Optional[str] = None,
    attach: bool = False
) -> dict:
    """
    Create a new tmux session.

    Use this to bootstrap a tmux environment from non-tmux contexts
    (e.g., Claude Desktop) before using other conductor tools.

    Args:
        name: Session name
        start_dir: Working directory (default: current)
        command: Command to run in initial window (default: shell)
        attach: Whether to attach to session (default: False, detached)

    Returns:
        Dict with session info
    """
    args = ["tmux", "new-session", "-s", name, "-P",
            "-F", "#{session_id}|#{window_id}|#{pane_id}"]

    if not attach:
        args.append("-d")  # Detached

    if start_dir:
        args.extend(["-c", start_dir])

    if command:
        args.append(command)

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    parts = result.stdout.strip().split("|")
    return {
        "session": name,
        "session_id": parts[0] if len(parts) > 0 else None,
        "window_id": parts[1] if len(parts) > 1 else None,
        "pane_id": parts[2] if len(parts) > 2 else None,
        "attached": attach
    }


@mcp.tool()
def create_window(
    session: str,
    name: Optional[str] = None,
    start_dir: Optional[str] = None,
    command: Optional[str] = None
) -> dict:
    """
    Create a new window in an existing session.

    Args:
        session: Target session name
        name: Window name (optional)
        start_dir: Working directory (default: inherit from session)
        command: Command to run (default: shell)

    Returns:
        Dict with window info
    """
    args = ["tmux", "new-window", "-t", session, "-P",
            "-F", "#{window_id}|#{window_index}|#{pane_id}"]

    if name:
        args.extend(["-n", name])

    if start_dir:
        args.extend(["-c", start_dir])

    if command:
        args.append(command)

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    parts = result.stdout.strip().split("|")
    return {
        "session": session,
        "window_id": parts[0] if len(parts) > 0 else None,
        "window_index": int(parts[1]) if len(parts) > 1 else None,
        "pane_id": parts[2] if len(parts) > 2 else None,
        "name": name
    }


# ═══════════════════════════════════════════════════════════════
# PANE MANAGEMENT TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def split_pane(
    direction: str = "horizontal",
    target: Optional[str] = None,
    percentage: int = 50,
    start_dir: Optional[str] = None
) -> dict:
    """
    Split the current or target pane to create a new pane.

    Args:
        direction: "horizontal" (side-by-side) or "vertical" (stacked)
        target: Target pane ID (e.g., "%0") or session:window.pane. None = current pane.
        percentage: Size of new pane as percentage (default: 50)
        start_dir: Working directory for new pane (default: inherit)

    Returns:
        Dict with new pane info
    """
    args = ["tmux", "split-window"]

    # Direction flag
    if direction == "horizontal":
        args.append("-h")  # -h = horizontal split (side by side)
    else:
        args.append("-v")  # -v = vertical split (stacked)

    # Target pane
    if target:
        args.extend(["-t", target])

    # Working directory
    if start_dir:
        args.extend(["-c", start_dir])

    # Percentage (use -l with percentage calculation based on current size)
    # Note: -p flag has issues in some tmux versions, so we use default 50% split
    # by omitting size flags entirely (tmux defaults to even split)

    # Print new pane info
    args.extend(["-P", "-F", "#{pane_id}|#{pane_index}|#{pane_width}x#{pane_height}"])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    parts = result.stdout.strip().split("|")
    return {
        "pane_id": parts[0] if len(parts) > 0 else None,
        "pane_index": int(parts[1]) if len(parts) > 1 else None,
        "size": parts[2] if len(parts) > 2 else None
    }


@mcp.tool()
def create_grid(
    layout: str = "2x2",
    session: Optional[str] = None,
    start_dir: Optional[str] = None
) -> dict:
    """
    Create a grid layout of panes (e.g., 2x2, 3x1, 2x3).

    Starts from the current pane and splits to create the grid.
    Great for spawning multiple workers visually.

    Args:
        layout: Grid specification as "COLSxROWS" (e.g., "2x2", "3x1", "4x1")
        session: Target session (default: current)
        start_dir: Working directory for all panes (default: inherit)

    Returns:
        Dict with pane IDs in grid order (left-to-right, top-to-bottom)
    """
    try:
        cols, rows = map(int, layout.lower().split("x"))
    except ValueError:
        return {"error": f"Invalid layout format: {layout}. Use COLSxROWS (e.g., 2x2)"}

    total_panes = cols * rows
    if total_panes < 1 or total_panes > 16:
        return {"error": "Layout must create 1-16 panes"}

    # Get current pane as starting point
    target = f"{session}:" if session else ""

    result = subprocess.run(
        ["tmux", "display-message", "-t", target or ".", "-p", "#{pane_id}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"error": "Could not get current pane"}

    first_pane = result.stdout.strip()
    panes = [first_pane]

    # Create the grid by splitting
    # Strategy: First create all rows, then split each row into columns

    # Step 1: Create rows by vertical splits
    current_pane = first_pane
    for row in range(1, rows):
        split_result = split_pane(
            direction="vertical",
            target=current_pane,
            start_dir=start_dir
        )
        if "error" in split_result:
            return split_result
        # The new pane becomes the bottom, we stay at top for next split
        panes.append(split_result["pane_id"])

    # Step 2: Split each row into columns
    # We need to track which panes are "row starters"
    row_panes = [first_pane] + [p for p in panes[1:]]  # First pane of each row

    final_panes = []
    for row_idx, row_pane in enumerate(row_panes[:rows]):
        row_result = [row_pane]
        current = row_pane

        for col in range(1, cols):
            split_result = split_pane(
                direction="horizontal",
                target=current,
                start_dir=start_dir
            )
            if "error" in split_result:
                return split_result
            row_result.append(split_result["pane_id"])
            current = split_result["pane_id"]

        final_panes.extend(row_result)

    # Apply even layout
    layout_name = "tiled"
    if rows == 1:
        layout_name = "even-horizontal"
    elif cols == 1:
        layout_name = "even-vertical"

    subprocess.run(
        ["tmux", "select-layout", "-t", target or ".", layout_name],
        capture_output=True
    )

    return {
        "layout": layout,
        "panes": final_panes[:total_panes],
        "count": len(final_panes[:total_panes])
    }


@mcp.tool()
def list_panes(session: Optional[str] = None) -> list[dict]:
    """
    List all panes in a session or current window.

    Args:
        session: Session name (default: current session, all windows)

    Returns:
        List of pane info dicts
    """
    args = ["tmux", "list-panes", "-F",
            "#{pane_id}|#{pane_index}|#{window_index}|#{pane_width}|#{pane_height}|#{pane_current_command}|#{pane_current_path}|#{pane_active}"]

    if session:
        args.extend(["-s", "-t", session])  # -s = all panes in session
    else:
        args.append("-s")  # All panes in current session

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return []

    panes = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 8:
            pane_id = parts[0]
            # Check for Claude status
            status = None
            state_file = STATE_DIR / f"{pane_id.replace('%', '_')}.json"
            if state_file.exists():
                try:
                    with open(state_file) as f:
                        state = json.load(f)
                        status = state.get("status")
                except (json.JSONDecodeError, IOError):
                    pass  # State file corrupt or unreadable, continue without status

            panes.append({
                "pane_id": parts[0],
                "pane_index": int(parts[1]),
                "window_index": int(parts[2]),
                "width": int(parts[3]),
                "height": int(parts[4]),
                "command": parts[5],
                "path": parts[6],
                "active": parts[7] == "1",
                "claude_status": status
            })

    return panes


@mcp.tool()
def focus_pane(pane_id: str) -> str:
    """
    Switch focus to a specific pane.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5") or index

    Returns:
        Confirmation message
    """
    result = subprocess.run(
        ["tmux", "select-pane", "-t", pane_id],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to focus pane: {result.stderr.strip()}"

    return f"Focused pane: {pane_id}"


@mcp.tool()
def kill_pane(pane_id: str) -> str:
    """
    Kill a specific pane.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")

    Returns:
        Confirmation message
    """
    result = subprocess.run(
        ["tmux", "kill-pane", "-t", pane_id],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to kill pane: {result.stderr.strip()}"

    return f"Killed pane: {pane_id}"


@mcp.tool()
async def spawn_worker_in_pane(
    pane_id: str,
    issue_id: str,
    project_dir: str,
    profile_cmd: str = "claude",
    inject_context: bool = True
) -> dict:
    """
    Spawn a worker in an existing pane (created by split_pane or create_grid).

    Use this after create_grid() to populate panes with workers.

    Args:
        pane_id: Target pane ID (e.g., "%5")
        issue_id: Beads issue ID (e.g., "BD-abc")
        project_dir: Path to the main project directory
        profile_cmd: Command to run (default: "claude")
        inject_context: Whether to inject beads context (default: True)

    Returns:
        Dict with worker info
    """
    project_path = Path(project_dir).expanduser().resolve()
    worktree_path = project_path / ".worktrees" / issue_id
    branch_name = f"feature/{issue_id}"

    # 1. Create worktree if it doesn't exist
    if not worktree_path.exists():
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["git", "-C", str(project_path), "branch", "--list", branch_name],
            capture_output=True, text=True
        )

        if result.stdout.strip():
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 str(worktree_path), branch_name],
                check=True
            )
        else:
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 "-b", branch_name, str(worktree_path)],
                check=True
            )

    # 2. Change to worktree directory in the pane
    subprocess.run(
        ["tmux", "send-keys", "-t", pane_id, f"cd {worktree_path}", "Enter"],
        check=True
    )
    await asyncio.sleep(0.3)

    # 3. Launch Claude/Codex
    subprocess.run(
        ["tmux", "send-keys", "-t", pane_id, profile_cmd, "Enter"],
        check=True
    )

    # 4. Wait for Claude to boot
    await asyncio.sleep(4)

    # 5. Inject context if requested
    context_text = ""
    if inject_context:
        try:
            result = subprocess.run(
                ["bd", "show", issue_id, "--format", "json"],
                capture_output=True, text=True,
                cwd=str(project_path),
                env={**os.environ, "BEADS_WORKING_DIR": str(project_path)}
            )
            if result.returncode == 0:
                issue = json.loads(result.stdout)
                context_text = f"""Fix beads issue {issue_id}: "{issue.get('title', 'Unknown')}"

{issue.get('description', '')}

When done:
1. Run tests/build to verify
2. Commit your changes
3. Run: bd close {issue_id} --reason "Brief description of fix"
"""
        except Exception:
            context_text = f"Work on issue {issue_id}. When done: bd close {issue_id}"

    # 6. Send the keys
    if context_text:
        await send_keys(pane_id, context_text)

    return {
        "pane_id": pane_id,
        "issue_id": issue_id,
        "worktree": str(worktree_path),
        "branch": branch_name,
        "context_injected": bool(context_text)
    }


# ═══════════════════════════════════════════════════════════════
# SMART SPAWN (visible worker placement)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
async def smart_spawn(
    issue_id: str,
    project_dir: str,
    session: Optional[str] = None,
    target_pane: Optional[str] = None,
    profile_cmd: str = "claude",
    inject_context: bool = True
) -> dict:
    """
    Spawn a worker visibly in the current tmux session by auto-splitting panes.

    Intelligently decides where to place the worker:
    - Splits the largest pane if there's enough room
    - Prefers horizontal (side-by-side) splits
    - Creates a new window (tab) when no pane can be split

    Unlike spawn_worker() which creates detached sessions, this keeps workers
    visible in your current session as splits/tabs.

    Args:
        issue_id: Beads issue ID (e.g., "BD-abc")
        project_dir: Path to the main project directory
        session: Target tmux session (auto-detects if omitted)
        target_pane: Specific pane to split (auto-selects largest if omitted)
        profile_cmd: Command to run (default: "claude")
        inject_context: Whether to inject beads context (default: True)

    Returns:
        Dict with worker info + placement decision
    """
    config = load_config()
    min_w = config.get("min_pane_width", 80)
    min_h = config.get("min_pane_height", 24)

    # Resolve session
    if not session:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{session_name}"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            session = result.stdout.strip()
        else:
            return {"error": "Not in a tmux session. Provide session parameter or use spawn_worker() for detached sessions."}

    # Decide placement
    placement = _find_best_split(session, min_w, min_h, target_pane)
    action = placement["action"]

    project_path = Path(project_dir).expanduser().resolve()

    # Execute placement
    if action == "split_h":
        result = split_pane(
            direction="horizontal",
            target=placement["target_pane"],
            start_dir=str(project_path)
        )
    elif action == "split_v":
        result = split_pane(
            direction="vertical",
            target=placement["target_pane"],
            start_dir=str(project_path)
        )
    else:  # new_window
        result = create_window(
            session=session,
            name=issue_id,
            start_dir=str(project_path)
        )

    if "error" in result:
        return {"error": f"Failed to create pane: {result['error']}", "placement": placement}

    new_pane_id = result.get("pane_id")
    if not new_pane_id:
        return {"error": "No pane_id returned from split/window creation", "placement": placement}

    # Spawn worker in the new pane
    worker_info = await spawn_worker_in_pane(
        pane_id=new_pane_id,
        issue_id=issue_id,
        project_dir=project_dir,
        profile_cmd=profile_cmd,
        inject_context=inject_context
    )

    worker_info["placement"] = placement
    return worker_info


@mcp.tool()
async def smart_spawn_wave(
    issue_ids: str,
    project_dir: str,
    session: Optional[str] = None,
    profile_cmd: str = "claude",
    inject_context: bool = True
) -> dict:
    """
    Spawn multiple workers visibly, auto-splitting panes as needed.

    Each worker re-evaluates available space after the previous split,
    so panes fill up naturally — splits when there's room, new windows when not.

    Args:
        issue_ids: Comma-separated beads issue IDs (e.g., "BD-abc,BD-def,BD-ghi")
        project_dir: Path to the main project directory
        session: Target tmux session (auto-detects if omitted)
        profile_cmd: Command to run (default: "claude")
        inject_context: Whether to inject beads context (default: True)

    Returns:
        Summary with total/spawned/failed counts and per-worker results
    """
    config = load_config()
    max_workers = config.get("max_concurrent_workers", 4)

    ids = [i.strip() for i in issue_ids.split(",") if i.strip()]
    if not ids:
        return {"error": "No issue IDs provided"}

    if len(ids) > max_workers:
        return {
            "error": f"Requested {len(ids)} workers but max_concurrent_workers is {max_workers}. "
                     f"Increase with set_config or reduce issue count.",
            "requested": len(ids),
            "max": max_workers
        }

    results = []
    spawned = 0
    failed = 0

    for issue_id in ids:
        worker_result = await smart_spawn(
            issue_id=issue_id,
            project_dir=project_dir,
            session=session,
            profile_cmd=profile_cmd,
            inject_context=inject_context
        )

        if "error" in worker_result:
            failed += 1
            results.append({"issue_id": issue_id, "status": "failed", "error": worker_result["error"]})
        else:
            spawned += 1
            results.append({
                "issue_id": issue_id,
                "status": "spawned",
                "pane_id": worker_result.get("pane_id"),
                "placement": worker_result.get("placement", {}).get("action")
            })

    return {
        "total": len(ids),
        "spawned": spawned,
        "failed": failed,
        "workers": results
    }


# ═══════════════════════════════════════════════════════════════
# REAL-TIME MONITORING (pipe-pane)
# ═══════════════════════════════════════════════════════════════

WATCH_DIR = Path("/tmp/conductor-watch")
WATCH_DIR.mkdir(exist_ok=True)


@mcp.tool()
def watch_pane(
    pane_id: str,
    output_file: Optional[str] = None
) -> dict:
    """
    Start streaming a pane's output to a file for real-time monitoring.

    Uses tmux pipe-pane to capture all output as it happens.
    Much more efficient than polling capture_pane().

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")
        output_file: File path for output (default: /tmp/conductor-watch/{pane_id}.log)

    Returns:
        Dict with output file path and status
    """
    if output_file is None:
        safe_id = pane_id.replace("%", "pane-")
        output_file = str(WATCH_DIR / f"{safe_id}.log")

    # Ensure output file exists and is empty
    Path(output_file).write_text("")

    # Start piping output to file
    result = subprocess.run(
        ["tmux", "pipe-pane", "-t", pane_id, f"cat >> {output_file}"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    return {
        "pane_id": pane_id,
        "output_file": output_file,
        "status": "watching"
    }


@mcp.tool()
def stop_watch(pane_id: str) -> str:
    """
    Stop streaming a pane's output.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")

    Returns:
        Confirmation message
    """
    # Empty pipe-pane command stops the pipe
    result = subprocess.run(
        ["tmux", "pipe-pane", "-t", pane_id],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to stop watch: {result.stderr.strip()}"

    return f"Stopped watching pane: {pane_id}"


@mcp.tool()
def read_watch(
    pane_id: str,
    lines: int = 50,
    output_file: Optional[str] = None
) -> str:
    """
    Read recent output from a watched pane's log file.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")
        lines: Number of lines from end to read (default: 50)
        output_file: Custom output file path (default: auto-detected)

    Returns:
        Recent output from the watch file
    """
    if output_file is None:
        safe_id = pane_id.replace("%", "pane-")
        output_file = str(WATCH_DIR / f"{safe_id}.log")

    path = Path(output_file)
    if not path.exists():
        return f"No watch file found for {pane_id}. Start with watch_pane() first."

    # Read last N lines
    try:
        content = path.read_text()
        all_lines = content.splitlines()
        return "\n".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading watch file: {e}"


# ═══════════════════════════════════════════════════════════════
# SYNCHRONIZATION (wait-for channels)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def wait_for_signal(
    channel: str,
    timeout_s: int = 300
) -> dict:
    """
    Wait for a worker to signal completion on a channel.

    Workers can signal with: tmux wait-for -S {channel}
    or use send_signal() tool.

    Args:
        channel: Channel name (e.g., "done-BD-abc", "worker-1-complete")
        timeout_s: Timeout in seconds (default: 300 = 5 minutes)

    Returns:
        Dict with status and timing info
    """
    import time
    start = time.time()

    try:
        proc = await asyncio.create_subprocess_exec(
            "tmux", "wait-for", channel,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        elapsed = time.time() - start

        return {
            "channel": channel,
            "status": "received",
            "elapsed_s": round(elapsed, 2)
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "channel": channel,
            "status": "timeout",
            "timeout_s": timeout_s
        }
    except Exception as e:
        return {
            "channel": channel,
            "status": "error",
            "error": str(e)
        }


@mcp.tool()
def send_signal(channel: str) -> str:
    """
    Send a signal on a channel (unblocks any wait_for_signal listeners).

    Use this when a worker completes its task.

    Args:
        channel: Channel name (e.g., "done-BD-abc")

    Returns:
        Confirmation message
    """
    result = subprocess.run(
        ["tmux", "wait-for", "-S", channel],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to send signal: {result.stderr.strip()}"

    return f"Signal sent: {channel}"


# ═══════════════════════════════════════════════════════════════
# POPUP NOTIFICATIONS (display-popup)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def show_popup(
    message: str,
    title: str = "Conductor",
    width: int = 50,
    height: int = 10,
    duration_s: int = 3,
    target: Optional[str] = None
) -> str:
    """
    Show a floating popup notification in tmux.

    Args:
        message: Message to display
        title: Popup title (default: "Conductor")
        width: Popup width in columns (default: 50)
        height: Popup height in rows (default: 10)
        duration_s: How long to show (default: 3 seconds)
        target: Target pane/session (default: current)

    Returns:
        Confirmation message
    """
    # Build the command to run inside popup
    # Using printf for better escaping, then sleep for duration
    escaped_msg = message.replace("'", "'\\''")
    popup_cmd = f"printf '%s\\n' '{escaped_msg}'; sleep {duration_s}"

    args = ["tmux", "display-popup"]

    if target:
        args.extend(["-t", target])

    args.extend([
        "-T", title,
        "-w", str(width),
        "-h", str(height),
        "-E", popup_cmd
    ])

    # Run in background so it doesn't block
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return f"Popup shown: {message[:30]}{'...' if len(message) > 30 else ''}"


@mcp.tool()
def show_status_popup(
    workers: Optional[list] = None,
    target: Optional[str] = None
) -> str:
    """
    Show a popup with current worker status summary.

    Args:
        workers: List of worker dicts (from list_workers). If None, fetches fresh.
        target: Target pane/session (default: current)

    Returns:
        Confirmation message
    """
    if workers is None:
        workers = list_workers()

    if not workers:
        message = "No active workers"
    else:
        lines = ["WORKER STATUS", "=" * 30]
        for w in workers:
            status = w.get("claude_status") or "unknown"
            attached = "•" if w.get("attached") else " "
            lines.append(f"{attached} {w['session']}: {status}")
        lines.append("=" * 30)
        lines.append(f"Total: {len(workers)} workers")
        message = "\n".join(lines)

    return show_popup(
        message=message,
        title="Worker Status",
        width=40,
        height=min(len(workers) + 6, 20),
        duration_s=5,
        target=target
    )


# ═══════════════════════════════════════════════════════════════
# HOOKS (event-driven automation)
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def set_pane_hook(
    event: str,
    command: str,
    session: Optional[str] = None
) -> str:
    """
    Set a hook to run a command when a pane event occurs.

    Args:
        event: Event name (pane-died, pane-exited, pane-focus-in, pane-focus-out)
        command: Shell command to run when event fires
        session: Session to attach hook to (default: global)

    Returns:
        Confirmation message
    """
    valid_events = [
        "pane-died", "pane-exited", "pane-focus-in", "pane-focus-out",
        "pane-mode-changed", "pane-set-clipboard"
    ]

    if event not in valid_events:
        return f"Invalid event. Valid events: {', '.join(valid_events)}"

    args = ["tmux", "set-hook"]

    if session:
        args.extend(["-t", session])
    else:
        args.append("-g")  # Global hook

    args.extend([event, f"run-shell '{command}'"])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Failed to set hook: {result.stderr.strip()}"

    scope = f"session {session}" if session else "global"
    return f"Hook set ({scope}): {event} -> {command}"


@mcp.tool()
def clear_hook(
    event: str,
    session: Optional[str] = None
) -> str:
    """
    Clear a previously set hook.

    Args:
        event: Event name to clear
        session: Session (default: global)

    Returns:
        Confirmation message
    """
    args = ["tmux", "set-hook"]

    if session:
        args.extend(["-t", session, "-u", event])
    else:
        args.extend(["-gu", event])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Failed to clear hook: {result.stderr.strip()}"

    return f"Hook cleared: {event}"


@mcp.tool()
def list_hooks(session: Optional[str] = None) -> list[dict]:
    """
    List active hooks.

    Args:
        session: Session (default: global)

    Returns:
        List of hook definitions
    """
    args = ["tmux", "show-hooks"]

    if session:
        args.extend(["-t", session])
    else:
        args.append("-g")

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return []

    hooks = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Format: "event command"
        parts = line.split(" ", 1)
        if len(parts) >= 2:
            hooks.append({
                "event": parts[0],
                "command": parts[1]
            })

    return hooks


# ═══════════════════════════════════════════════════════════════
# PANE RESIZING & LAYOUT
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def resize_pane(
    pane_id: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    adjust_x: Optional[int] = None,
    adjust_y: Optional[int] = None
) -> str:
    """
    Resize a pane to specific dimensions or by relative amounts.

    Args:
        pane_id: Pane ID (e.g., "%0")
        width: Set absolute width in columns
        height: Set absolute height in rows
        adjust_x: Adjust width by +/- columns (e.g., 10 or -5)
        adjust_y: Adjust height by +/- rows (e.g., 10 or -5)

    Returns:
        Confirmation message
    """
    args = ["tmux", "resize-pane", "-t", pane_id]

    if width is not None:
        args.extend(["-x", str(width)])
    if height is not None:
        args.extend(["-y", str(height)])
    if adjust_x is not None:
        if adjust_x > 0:
            args.extend(["-R", str(adjust_x)])
        else:
            args.extend(["-L", str(abs(adjust_x))])
    if adjust_y is not None:
        if adjust_y > 0:
            args.extend(["-D", str(adjust_y)])
        else:
            args.extend(["-U", str(abs(adjust_y))])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Failed to resize: {result.stderr.strip()}"

    return f"Resized pane: {pane_id}"


@mcp.tool()
def zoom_pane(pane_id: str) -> str:
    """
    Toggle zoom (fullscreen) for a pane.

    When zoomed, the pane fills the entire window.
    Call again to unzoom.

    Args:
        pane_id: Pane ID (e.g., "%0")

    Returns:
        Confirmation message
    """
    result = subprocess.run(
        ["tmux", "resize-pane", "-t", pane_id, "-Z"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Failed to toggle zoom: {result.stderr.strip()}"

    return f"Toggled zoom for pane: {pane_id}"


@mcp.tool()
def apply_layout(
    layout: str,
    target: Optional[str] = None
) -> str:
    """
    Apply a layout to organize panes evenly.

    Args:
        layout: Layout name - one of:
            - "tiled" (equal grid)
            - "even-horizontal" (side by side, equal width)
            - "even-vertical" (stacked, equal height)
            - "main-horizontal" (one large on top, others below)
            - "main-vertical" (one large on left, others right)
        target: Target window (default: current)

    Returns:
        Confirmation message
    """
    valid_layouts = [
        "tiled", "even-horizontal", "even-vertical",
        "main-horizontal", "main-vertical"
    ]

    if layout not in valid_layouts:
        return f"Invalid layout. Valid options: {', '.join(valid_layouts)}"

    args = ["tmux", "select-layout"]

    if target:
        args.extend(["-t", target])

    args.append(layout)

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Failed to apply layout: {result.stderr.strip()}"

    return f"Applied layout: {layout}"


@mcp.tool()
def rebalance_panes(target: Optional[str] = None) -> str:
    """
    Rebalance panes to equal sizes using tiled layout.

    Useful after killing a pane to reorganize the remaining ones.

    Args:
        target: Target window (default: current)

    Returns:
        Confirmation message with pane count
    """
    # Get pane count first
    args = ["tmux", "list-panes"]
    if target:
        args.extend(["-t", target])

    result = subprocess.run(args, capture_output=True, text=True)
    pane_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    # Apply tiled layout
    apply_result = apply_layout("tiled", target)

    if "Failed" in apply_result:
        return apply_result

    return f"Rebalanced {pane_count} panes with tiled layout"


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
def get_config() -> dict:
    """
    Get current conductor configuration.

    Returns config including:
    - max_concurrent_workers
    - default_layout
    - voice settings (default voice, rate, pitch, random_per_worker)
    - delay settings
    - current worker voice assignments
    """
    return load_config()


@mcp.tool()
def set_config(
    max_concurrent_workers: Optional[int] = None,
    default_layout: Optional[str] = None,
    default_voice: Optional[str] = None,
    voice_rate: Optional[str] = None,
    voice_pitch: Optional[str] = None,
    random_voices: Optional[bool] = None,
    send_keys_delay_ms: Optional[int] = None,
    claude_boot_delay_s: Optional[int] = None
) -> dict:
    """
    Update conductor configuration.

    Args:
        max_concurrent_workers: Max workers to spawn (default: 4)
        default_layout: Default grid layout (default: "2x2")
        default_voice: Default TTS voice
        voice_rate: Speech rate (e.g., "+0%", "+20%", "-10%")
        voice_pitch: Voice pitch (e.g., "+0Hz", "+50Hz")
        random_voices: Assign unique voices per worker (default: True)
        send_keys_delay_ms: Delay before Enter key when submit=True (default: 800)
        claude_boot_delay_s: Wait time for Claude to boot (default: 4)

    Returns:
        Updated config
    """
    config = load_config()

    if max_concurrent_workers is not None:
        config["max_concurrent_workers"] = max_concurrent_workers
    if default_layout is not None:
        config["default_layout"] = default_layout
    if default_voice is not None:
        config["voice"]["default"] = default_voice
    if voice_rate is not None:
        config["voice"]["rate"] = voice_rate
    if voice_pitch is not None:
        config["voice"]["pitch"] = voice_pitch
    if random_voices is not None:
        config["voice"]["random_per_worker"] = random_voices
    if send_keys_delay_ms is not None:
        config["delays"]["send_keys_ms"] = send_keys_delay_ms
    if claude_boot_delay_s is not None:
        config["delays"]["claude_boot_s"] = claude_boot_delay_s

    save_config(config)
    return config


@mcp.tool()
def list_voices() -> list[dict]:
    """
    List available TTS voices with current assignments.

    Returns list of voices showing which are assigned to workers.
    """
    config = load_config()
    assignments = config.get("worker_voice_assignments", {})

    # Reverse mapping: voice -> worker
    voice_to_worker = {v: k for k, v in assignments.items()}

    voices = []
    for voice in VOICE_POOL:
        voices.append({
            "voice": voice,
            "assigned_to": voice_to_worker.get(voice),
            "is_default": voice == config["voice"]["default"]
        })

    return voices


@mcp.tool()
async def test_voice(voice: str, text: str = "Hello, I am your conductor assistant.") -> str:
    """
    Test a specific TTS voice.

    Args:
        voice: Voice name from list_voices()
        text: Text to speak (default: greeting)

    Returns:
        Confirmation
    """
    return await speak(text=text, voice=voice, blocking=True)


@mcp.tool()
def reset_voice_assignments() -> str:
    """
    Clear all worker voice assignments.

    Use this to reset the voice pool when starting fresh.
    """
    config = load_config()
    config["worker_voice_assignments"] = {}
    config["voice_pool_index"] = 0
    save_config(config)
    return "Voice assignments cleared"


# ═══════════════════════════════════════════════════════════════
# PROMPTS (appear in /slash command menu)
# ═══════════════════════════════════════════════════════════════

@mcp.prompt(
    name="spawn-wave",
    title="Spawn Worker Wave",
    description="Create a grid and spawn workers for ready beads issues"
)
def prompt_spawn_wave(project_dir: str, layout: str = "2x2") -> list[dict]:
    """Prompt to spawn a wave of workers for ready issues."""
    return [
        {
            "role": "user",
            "content": f"""Spawn workers for ready beads issues, visible in the current session.

Project: {project_dir}

Steps:
1. Run `bd ready` to get ready issues (not blocked)
2. Collect issue IDs (up to max_concurrent_workers)
3. Use smart_spawn_wave(issue_ids="ID1,ID2,...", project_dir="{project_dir}") to spawn all at once
   - Workers appear as splits in the current window, overflowing to new tabs when needed
4. Announce each spawn with speak()
5. Report which workers were spawned and where (split vs new window)

Use the conductor MCP tools: smart_spawn_wave, speak, list_panes

Note: For manual grid control, create_grid() + spawn_worker_in_pane() still work."""
        }
    ]


@mcp.prompt(
    name="worker-status",
    title="Check Worker Status",
    description="Get status of all active workers with audio summary"
)
def prompt_worker_status() -> list[dict]:
    """Prompt to check all worker statuses."""
    return [
        {
            "role": "user",
            "content": """Check the status of all active workers.

Steps:
1. Use list_workers() to get all tmux sessions
2. For each worker, use get_worker_status() to get Claude's state
3. Summarize: how many idle, processing, using tools
4. Announce summary with speak()

Report format:
- Worker name | Status | Current tool | Context %"""
        }
    ]


@mcp.prompt(
    name="orchestrate",
    title="Full Orchestration",
    description="Run complete orchestration: plan issues, spawn workers, monitor"
)
def prompt_orchestrate(project_dir: str) -> list[dict]:
    """Prompt for full orchestration workflow."""
    return [
        {
            "role": "user",
            "content": f"""Run full orchestration for {project_dir}.

Phase 1 - Planning:
1. Run `bd ready` to see available work
2. Run `bd blocked` to see what's waiting on dependencies
3. Decide how many workers to spawn (up to max_concurrent_workers)

Phase 2 - Spawning:
1. Use smart_spawn_wave(issue_ids="ID1,ID2,...", project_dir="{project_dir}") to spawn all workers
   - Workers appear as visible splits in the current session, overflowing to new tabs
2. Announce "Wave started with N workers"

Phase 3 - Monitoring:
1. Periodically check worker status with list_panes()
2. When a worker shows idle status, check if issue is closed
3. Announce completions with speak()

Use conductor MCP tools throughout. Be the conductor!"""
        }
    ]


@mcp.prompt(
    name="announce",
    title="Make Announcement",
    description="Speak a message aloud via TTS"
)
def prompt_announce(message: str) -> list[dict]:
    """Simple prompt to make a TTS announcement."""
    return [
        {
            "role": "user",
            "content": f"Use the speak() tool to announce: {message}"
        }
    ]


@mcp.prompt(
    name="options",
    title="Conductor Options",
    description="View and adjust conductor settings (voices, delays, workers)"
)
def prompt_options() -> list[dict]:
    """Prompt to view and modify conductor settings."""
    return [
        {
            "role": "user",
            "content": """Show conductor configuration and let me adjust settings.

1. First, call get_config() to show current settings
2. Call list_voices() to show available TTS voices and assignments
3. Present the settings in a nice format:

**Current Configuration**
- Max workers: X
- Default layout: XxX
- Voice: [name] at [rate] speed
- Random voices per worker: yes/no
- Prompt delay: Xms
- Boot delay: Xs

**Voice Assignments**
[table of voice -> worker]

**Available Actions**
- Change max workers
- Change default voice
- Adjust voice speed (+20%, -10%, etc.)
- Toggle random voices
- Test a voice
- Reset voice assignments

Ask me what I'd like to change, then use set_config() to apply changes.
After changes, use speak() to confirm with "Settings updated"."""
        }
    ]


@mcp.prompt(
    name="test-voices",
    title="Test TTS Voices",
    description="Listen to and compare available TTS voices"
)
def prompt_test_voices() -> list[dict]:
    """Prompt to test different TTS voices."""
    return [
        {
            "role": "user",
            "content": """Help me pick a TTS voice.

1. Call list_voices() to see available voices
2. For each voice category (US, UK, Australian), test one with test_voice()
3. Use a short test phrase that shows personality
4. After testing, ask which voice I'd like as default
5. Update config with set_config(default_voice=...)

Good test phrases:
- "Worker one reporting for duty"
- "Task complete, moving to next issue"
- "Warning: context usage at 75 percent" """
        }
    ]


@mcp.prompt(
    name="kill-all",
    title="Kill All Workers",
    description="Stop all active worker sessions"
)
def prompt_kill_all() -> list[dict]:
    """Prompt to kill all workers."""
    return [
        {
            "role": "user",
            "content": """Kill all active worker sessions.

1. Call list_workers() to see active sessions
2. For each worker, call kill_worker(session)
3. Call reset_voice_assignments() to free up voices
4. Announce "All workers terminated" with speak()
5. Report how many workers were killed"""
        }
    ]


if __name__ == "__main__":
    mcp.run()
