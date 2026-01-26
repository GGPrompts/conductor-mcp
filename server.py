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
DEFAULT_DELAY_MS = 800
DEFAULT_VOICE = "en-US-AriaNeural"
DEFAULT_RATE = "+0%"

# Ensure directories exist
STATE_DIR.mkdir(exist_ok=True)
AUDIO_CACHE_DIR.mkdir(exist_ok=True)


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
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    blocking: bool = False
) -> str:
    """
    Speak text aloud using edge-tts.

    Args:
        text: Text to speak
        voice: Edge TTS voice (default: en-US-AriaNeural)
        rate: Speech rate (e.g., "+0%", "+20%", "-10%")
        blocking: Wait for speech to complete (default: False)

    Returns:
        Confirmation message
    """
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


if __name__ == "__main__":
    mcp.run()
