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

    # Play audio
    try:
        if blocking:
            subprocess.run(
                ["mpv", "--no-video", "--really-quiet", str(cache_file)],
                check=True
            )
        else:
            subprocess.Popen(
                ["mpv", "--no-video", "--really-quiet", str(cache_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except FileNotFoundError:
        return f"Audio cached at {cache_file} but mpv not found for playback"

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


if __name__ == "__main__":
    mcp.run()
