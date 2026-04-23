#!/usr/bin/env python3
"""
conductor.server — Terminal-only orchestration MCP server.

Thin FastMCP wrapper around conductor.core. All pure helpers (config, voice
allocation, layout math, context readers) live in conductor.core; all shared
return-shape types live in conductor.protocol. The MCP @tool decorators in
this file register the agent-facing surface.

Brings TabzChrome's orchestration superpowers to any terminal.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from conductor.core import (
    DEFAULT_DELAY_MS,
    _find_best_split,
    apply_layout_impl,
    capture_worker_output_impl,
    clear_hook_impl,
    create_grid_impl,
    create_session_impl,
    create_window_impl,
    focus_pane_impl,
    get_config_impl,
    get_context_percent_impl,
    get_worker_status_impl,
    get_worker_voice,
    get_workers_with_capacity_impl,
    kill_pane_impl,
    kill_worker_impl,
    list_hooks_impl,
    list_panes_impl,
    list_workers_impl,
    load_config,
    read_watch_impl,
    rebalance_panes_impl,
    resize_pane_impl,
    resolve_profile,
    send_keys_impl,
    set_pane_hook_impl,
    show_popup_impl,
    show_status_popup_impl,
    spawn_worker_in_pane_impl,
    speak_impl,
    split_pane_impl,
    stop_watch_impl,
    watch_pane_impl,
    zoom_pane_impl,
)
from conductor.protocol import (
    ContextPercent,
    HookInfo,
    PaneInfo,
    SpawnResult,
    WorkerInfo,
    WorkerStatus,
)

# Initialize MCP server
mcp = FastMCP("conductor")

# ───────────────────────────────────────────────────────────────
# Shim tools — prefer `cm` CLI (cm-aax.9)
# ───────────────────────────────────────────────────────────────
# The following 29 @mcp.tool registrations are thin shims delegating to
# conductor.core.*_impl helpers. The canonical surface for these verbs is
# the `cm` CLI — MCP shims stay registered during soak for backward
# compatibility and will be removed in a future cleanup. The 5 primitives
# that remain MCP-first are: spawn_worker, smart_spawn, smart_spawn_wave,
# wait_for_signal, send_signal.
#
# Fire-and-forget shims (23, from cm-aax.5/.6/.7):
#   send_keys, speak, kill_worker, kill_pane, focus_pane, show_popup,
#   show_status_popup, create_session, create_window, split_pane,
#   create_grid, spawn_worker_in_pane, resize_pane, zoom_pane,
#   apply_layout, rebalance_panes, watch_pane, stop_watch, read_watch,
#   set_pane_hook, clear_hook, list_hooks, get_config
# Polling shims (6, from cm-aax.9):
#   list_workers, list_panes, get_worker_status, get_context_percent,
#   get_workers_with_capacity, capture_worker_output


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
    return send_keys_impl(session, keys, submit=submit, delay_ms=delay_ms)


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


@mcp.tool()
def speak(
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
    return speak_impl(
        text,
        voice=voice,
        rate=rate,
        worker_id=worker_id,
        blocking=blocking,
        priority=priority,
    )


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
    return kill_worker_impl(session, cleanup_worktree=cleanup_worktree, project_dir=project_dir)


@mcp.tool()
def list_workers() -> list[dict]:
    """
    List active tmux sessions that look like workers. Prefer `cm list workers`.

    Returns:
        List of worker session info
    """
    return list_workers_impl()


@mcp.tool()
def get_worker_status(session: str) -> Optional[dict]:
    """
    Get Claude's current status for a worker session. Prefer `cm worker status <session>`.

    Reads from /tmp/claude-code-state/{session}.json written by Claude hooks.

    Args:
        session: tmux session name

    Returns:
        Status dict or None if not found
    """
    return get_worker_status_impl(session)


@mcp.tool()
def get_context_percent(target: str) -> dict:
    """
    Get the context usage percentage from a Claude Code session.
    Prefer `cm context <target>`.

    Attempts to read from state files first (accurate, from statusline script),
    then falls back to parsing the visible terminal status line.

    Args:
        target: tmux session name or pane ID (e.g., "BD-abc" or "%5")

    Returns:
        Dict with context_percent (int 0-100), source ("state_file" or "terminal_scrape"),
        and additional token info when available from state files.
    """
    return get_context_percent_impl(target)


@mcp.tool()
def get_workers_with_capacity(threshold: int = 60) -> dict:
    """
    Find workers that have remaining context capacity for more tasks.
    Prefer `cm worker capacity --threshold N`.

    Checks all active workers and returns those below the context threshold.
    Useful for deciding whether to reuse existing workers vs spawn new ones.

    Args:
        threshold: Context % below which a worker has capacity (default: 60)

    Returns:
        Dict with workers_with_capacity list and summary stats
    """
    return get_workers_with_capacity_impl(threshold=threshold)


@mcp.tool()
def capture_worker_output(session: str, lines: int = 50) -> str:
    """
    Capture recent output from a worker's tmux pane. Prefer `cm capture <session>`.

    Args:
        session: tmux session name
        lines: Number of lines to capture (default: 50)

    Returns:
        Captured terminal output
    """
    return capture_worker_output_impl(session, lines=lines)


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
    return create_session_impl(
        name,
        start_dir=start_dir,
        command=command,
        attach=attach,
    )


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
    return create_window_impl(
        session,
        name=name,
        start_dir=start_dir,
        command=command,
    )


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
    return split_pane_impl(
        direction=direction,
        target=target,
        percentage=percentage,
        start_dir=start_dir,
    )


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
    return create_grid_impl(
        layout=layout,
        session=session,
        start_dir=start_dir,
    )


@mcp.tool()
def list_panes(session: Optional[str] = None) -> list[dict]:
    """
    List all panes in a session or current window. Prefer `cm list panes`.

    Args:
        session: Session name (default: current session, all windows)

    Returns:
        List of pane info dicts (see conductor.protocol.PaneInfo)
    """
    return list_panes_impl(session)


@mcp.tool()
def focus_pane(pane_id: str) -> str:
    """
    Switch focus to a specific pane.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5") or index

    Returns:
        Confirmation message
    """
    return focus_pane_impl(pane_id)


@mcp.tool()
def kill_pane(pane_id: str) -> str:
    """
    Kill a specific pane.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")

    Returns:
        Confirmation message
    """
    return kill_pane_impl(pane_id)


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
    return spawn_worker_in_pane_impl(
        pane_id=pane_id,
        issue_id=issue_id,
        project_dir=project_dir,
        profile_cmd=profile_cmd,
        inject_context=inject_context,
    )


# ═══════════════════════════════════════════════════════════════
# SMART SPAWN (visible worker placement)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
async def smart_spawn(
    issue_id: str,
    project_dir: str = "",
    session: Optional[str] = None,
    target_pane: Optional[str] = None,
    profile: str = "claude",
    profile_cmd: str = "",
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
        project_dir: Path to the main project directory (falls back to profile dir or default_dir)
        session: Target tmux session (auto-detects if omitted)
        target_pane: Specific pane to split (auto-selects largest if omitted)
        profile: Profile name from config (default: "claude"). Managed in conductor-tui Settings.
        profile_cmd: Raw command override (backward compat, takes precedence over profile)
        inject_context: Whether to inject beads context (default: True)

    Returns:
        Dict with worker info + placement decision
    """
    # Resolve profile — explicit profile_cmd overrides profile name
    resolved = resolve_profile(profile_cmd if profile_cmd else profile)
    effective_cmd = resolved["command"]

    # Resolve project_dir — explicit > profile pinned dir > default_dir
    effective_dir = project_dir or resolved["dir"] or ""
    if not effective_dir:
        return {"error": "No project_dir provided and no default_dir configured. Edit ~/.config/conductor/config.json or use the conductor-tui Settings panel."}

    config = load_config()
    min_w = config.get("min_pane_width", 40)
    min_h = config.get("min_pane_height", 12)

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

    project_path = Path(effective_dir).expanduser().resolve()

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
        project_dir=effective_dir,
        profile_cmd=effective_cmd,
        inject_context=inject_context
    )

    worker_info["placement"] = placement
    worker_info["profile"] = profile_cmd if profile_cmd else profile
    return worker_info


@mcp.tool()
async def smart_spawn_wave(
    issue_ids: str,
    project_dir: str = "",
    session: Optional[str] = None,
    profile: str = "claude",
    profile_cmd: str = "",
    inject_context: bool = True
) -> dict:
    """
    Spawn multiple workers visibly, auto-splitting panes as needed.

    Each worker re-evaluates available space after the previous split,
    so panes fill up naturally — splits when there's room, new windows when not.

    Args:
        issue_ids: Comma-separated beads issue IDs (e.g., "BD-abc,BD-def,BD-ghi")
        project_dir: Path to the main project directory (falls back to profile dir or default_dir)
        session: Target tmux session (auto-detects if omitted)
        profile: Profile name from config (default: "claude"). Managed in conductor-tui Settings.
        profile_cmd: Raw command override (backward compat, takes precedence over profile)
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
            profile=profile,
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
    return watch_pane_impl(pane_id, output_file=output_file)


@mcp.tool()
def stop_watch(pane_id: str) -> str:
    """
    Stop streaming a pane's output.

    Args:
        pane_id: Pane ID (e.g., "%0", "%5")

    Returns:
        Confirmation message
    """
    return stop_watch_impl(pane_id)


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
    return read_watch_impl(pane_id, lines=lines, output_file=output_file)


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
    return show_popup_impl(
        message=message,
        title=title,
        width=width,
        height=height,
        duration_s=duration_s,
        target=target,
    )


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
    return show_status_popup_impl(workers=workers, target=target)


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
    return set_pane_hook_impl(event, command, session=session)


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
    return clear_hook_impl(event, session=session)


@mcp.tool()
def list_hooks(session: Optional[str] = None) -> list[dict]:
    """
    List active hooks.

    Args:
        session: Session (default: global)

    Returns:
        List of hook definitions
    """
    return list_hooks_impl(session=session)


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
    return resize_pane_impl(
        pane_id,
        width=width,
        height=height,
        adjust_x=adjust_x,
        adjust_y=adjust_y,
    )


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
    return zoom_pane_impl(pane_id)


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
    return apply_layout_impl(layout, target=target)


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
    return rebalance_panes_impl(target=target)


# ═══════════════════════════════════════════════════════════════
# PROFILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════
# User-facing profile CRUD moved to conductor-tui Settings panel (cm-3gw).
# Claude orchestration code continues to consume profiles via resolve_profile()
# reading the canonical config file.


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
    return get_config_impl()


# User-facing voice tools (list_voices, test_voice, reset_voice_assignments)
# and the user-facing params of set_config (voice_rate, voice_pitch, default_voice,
# random_voices, default_layout, default_dir, send_keys_delay_ms, claude_boot_delay_s)
# have been moved to the conductor-tui Settings panel (cm-3gw).
# set_config is removed entirely as Claude doesn't need to mutate config; orchestration
# reads via get_config() and resolve_profile() instead.


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
4. Announce each spawn with `cm speak "..."`
5. Inspect layout with `cm list panes` (TSV) and report which workers were spawned and where (split vs new window)

MCP primitives: smart_spawn_wave (orchestration). Everything else — speak,
list_panes, kill_worker, send_keys, etc. — is canonical on the `cm` CLI.
Run `cm --help` for the full verb list.

Note: For manual grid control, use `cm grid 2x2` + `cm spawn in-pane <pane_id> <issue_id> <project_dir>`."""
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
1. Run `cm list workers` (TSV: session, created, windows, attached, claude_status)
2. For each session, run `cm worker status <session> --json` for Claude's state
3. Run `cm context <session>` to get context % per worker
4. Summarize: how many idle, processing, using tools
5. Announce summary with `cm speak "..."`

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
2. Announce "Wave started with N workers" with `cm speak "..."`

Phase 3 - Monitoring:
1. Periodically check worker status with `cm list panes` and `cm worker capacity`
2. When a worker shows idle status, check if issue is closed
3. Announce completions with `cm speak "..."`

Orchestration primitives stay on MCP: smart_spawn_wave, wait_for_signal,
send_signal. Polling and fire-and-forget verbs (list, speak, send, kill,
capture, context, worker status, ...) are canonical on the `cm` CLI —
run `cm --help` for the full verb list. Be the conductor!"""
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
            "content": f"Run `cm speak \"{message}\"` to announce it via TTS."
        }
    ]


@mcp.prompt(
    name="options",
    title="Conductor Options",
    description="Open the conductor-tui Settings panel to adjust voices, profiles, and timing"
)
def prompt_options() -> list[dict]:
    """Prompt to view and modify conductor settings."""
    return [
        {
            "role": "user",
            "content": """Conductor settings live in the conductor-tui Settings panel.

Open it with: Ctrl+b o (tmux popup), then press 1 until the top panel cycles to the Settings tab.
From there you can pick voices, manage profiles, and tweak layout/timing.

For a read-only peek at the current config, run `cm config get` (TSV) or `cm config get --json`."""
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

1. Run `cm list workers` to see active sessions (TSV: session in col 1)
2. For each worker, run `cm kill worker <session>`
3. Announce "All workers terminated" with `cm speak "..."`
4. Report how many workers were killed

Note: voice assignments are managed by the user in the conductor-tui Settings panel."""
        }
    ]


def main() -> None:
    """Console-script entry point: run the FastMCP stdio server.

    Wired via pyproject.toml [project.scripts]:
        conductor-mcp = "conductor.server:main"
    """
    mcp.run()


if __name__ == "__main__":
    main()
