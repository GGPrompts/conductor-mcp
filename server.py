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
    "voice": {
        "default": "en-US-AriaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "random_per_worker": True,
    },
    "delays": {
        "send_prompt_ms": 800,
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


@mcp.tool()
async def send_prompt(
    session: str,
    text: str,
    delay_ms: int = DEFAULT_DELAY_MS
) -> str:
    """
    Send a prompt to a Claude/Codex tmux session with proper delay for submission.

    The delay between sending text and pressing Enter is critical - without it,
    Claude/Codex will create a newline instead of submitting the prompt.

    Args:
        session: tmux session name (e.g., "BD-abc" or "ctt-profile-uuid")
        text: The prompt text to send
        delay_ms: Milliseconds to wait before pressing Enter (default: 800)

    Returns:
        Confirmation message
    """
    # Send the text (escape any special tmux characters)
    escaped_text = text.replace("'", "'\\''")
    subprocess.run(
        ["tmux", "send-keys", "-t", session, "-l", text],
        check=True
    )

    # Wait for input detection
    await asyncio.sleep(delay_ms / 1000)

    # Press Enter to submit
    subprocess.run(
        ["tmux", "send-keys", "-t", session, "Enter"],
        check=True
    )

    return f"Sent prompt to {session} ({len(text)} chars, {delay_ms}ms delay)"


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

    # 6. Send the prompt
    if context_text:
        await send_prompt(session_name, context_text)

    return {
        "session": session_name,
        "worktree": str(worktree_path),
        "branch": branch_name,
        "context_injected": bool(context_text)
    }


@mcp.tool()
async def speak(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    worker_id: Optional[str] = None,
    blocking: bool = False
) -> str:
    """
    Speak text aloud using edge-tts.

    Args:
        text: Text to speak
        voice: Edge TTS voice (default from config, or worker's assigned voice)
        rate: Speech rate (e.g., "+0%", "+20%", "-10%")
        worker_id: If provided, uses this worker's unique assigned voice
        blocking: Wait for speech to complete (default: False)

    Returns:
        Confirmation message
    """
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

    # Try multiple audio players in order of preference
    players = [
        (["mpv", "--no-video", "--really-quiet", str(cache_file)], "mpv"),
        (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(cache_file)], "ffplay"),
        (["cvlc", "--play-and-exit", "--quiet", str(cache_file)], "vlc"),
    ]

    played = False
    for cmd, name in players:
        try:
            if blocking:
                subprocess.run(cmd, check=True, capture_output=True)
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            played = True
            break
        except FileNotFoundError:
            continue

    if not played:
        return f"Audio cached at {cache_file} - install mpv, ffplay, or vlc to play"

    return f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}"


@mcp.tool()
def kill_worker(session: str, cleanup_worktree: bool = False) -> str:
    """
    Kill a worker's tmux session and optionally clean up the worktree.

    Args:
        session: tmux session name
        cleanup_worktree: Also remove the git worktree (default: False)

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
                except:
                    pass

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
                except:
                    pass

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

    # 6. Send the prompt
    if context_text:
        await send_prompt(pane_id, context_text)

    return {
        "pane_id": pane_id,
        "issue_id": issue_id,
        "worktree": str(worktree_path),
        "branch": branch_name,
        "context_injected": bool(context_text)
    }


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
    send_prompt_delay_ms: Optional[int] = None,
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
        send_prompt_delay_ms: Delay before Enter key (default: 800)
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
    if send_prompt_delay_ms is not None:
        config["delays"]["send_prompt_ms"] = send_prompt_delay_ms
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
            "content": f"""Create a {layout} grid and spawn workers for ready beads issues.

Project: {project_dir}

Steps:
1. Run `bd ready` to get ready issues (not blocked)
2. Create a {layout} grid with create_grid()
3. For each pane and ready issue, use spawn_worker_in_pane()
4. Announce each spawn with speak()
5. Report which workers were spawned

Use the conductor MCP tools: create_grid, spawn_worker_in_pane, speak, list_panes"""
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
3. Decide how many workers to spawn (max 4 for 2x2 grid)

Phase 2 - Spawning:
1. Create grid layout with create_grid()
2. Spawn workers with spawn_worker_in_pane() for each issue
3. Announce "Wave started with N workers"

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
