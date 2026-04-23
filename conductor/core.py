"""conductor.core — pure helpers shared by MCP server and CLI.

No MCP decorators here, no click decorators here. Just tmux calls, config
parsing, voice allocation, layout math, and state-file readers. Both the
server and the CLI import from this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# Paths & constants
# ═══════════════════════════════════════════════════════════════

STATE_DIR = Path("/tmp/claude-code-state")
AUDIO_CACHE_DIR = Path("/tmp/conductor-audio-cache")
WATCH_DIR = Path("/tmp/conductor-watch")

# Canonical config path (cm-d64 decision)
CONFIG_DIR = Path.home() / ".config" / "conductor"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Legacy paths (read-once fallback on first run)
LEGACY_MCP_CONFIG = Path.home() / ".config" / "conductor-mcp" / "config.json"
LEGACY_TUI_CONFIG = Path.home() / ".config" / "conductor-tui" / "config.yaml"
LEGACY_AUDIO_SHIM = Path.home() / ".claude" / "audio-config.sh"

# Audio mutex — shared with audio-announcer.sh hooks
AUDIO_LOCK_FILE = Path("/tmp/claude-audio.lock")

# Defaults (used in function signatures)
DEFAULT_DELAY_MS = 800

# Ensure directories exist (predictable /tmp paths — tighten perms to prevent
# symlink / pre-populate attacks against md5 cache keys).
STATE_DIR.mkdir(mode=0o700, exist_ok=True, parents=True)
AUDIO_CACHE_DIR.mkdir(mode=0o700, exist_ok=True, parents=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
WATCH_DIR.mkdir(exist_ok=True)

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
        "volume": "+0%",
        "random_per_worker": True,
        "enabled": True,
    },
    "delays": {
        "send_keys_ms": 800,
        "claude_boot_s": 4,
    },
    "worker_voice_assignments": {},  # worker_id -> voice
    "voice_pool_index": 0,  # Tracks which voice to assign next
    "default_dir": "",  # Global fallback project dir for profiles without pinned dir
    "profiles": {
        "claude": {"command": "claude"},
        "codex": {"command": "codex"},
        "gemini": {"command": "gemini -i"},
        "copilot": {"command": "copilot"},
        "tfe": {"command": "tfe"},
        "lazygit": {"command": "lazygit"},
    },
}


# ═══════════════════════════════════════════════════════════════
# Config helpers
# ═══════════════════════════════════════════════════════════════

def _parse_audio_shim(path: Path) -> dict:
    """Parse ~/.claude/audio-config.sh (simple VAR=value lines) for migration."""
    result: dict = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                result[key] = value
    except (OSError, IOError):
        pass
    return result


def _migrate_legacy_configs() -> dict:
    """
    One-shot migrator for cm-d64 canonical config.

    Merges from legacy paths:
    - ~/.config/conductor-mcp/config.json -> mcp + audio + profiles sections
    - ~/.config/conductor-tui/config.yaml -> tui section (best-effort)
    - ~/.claude/audio-config.sh           -> audio section (VAR=value)

    Returns merged config. Leaves legacy files in place.
    """
    merged = DEFAULT_CONFIG.copy()

    # Legacy MCP config — pre-existing top-level shape (already matches current)
    if LEGACY_MCP_CONFIG.exists():
        try:
            with open(LEGACY_MCP_CONFIG) as f:
                legacy = json.load(f)
            for k, v in legacy.items():
                merged[k] = v
        except (json.JSONDecodeError, OSError):
            pass

    # Legacy audio shim (bash VAR=value) — overlay on voice/delay section
    if LEGACY_AUDIO_SHIM.exists():
        shim = _parse_audio_shim(LEGACY_AUDIO_SHIM)
        if shim:
            voice = merged.setdefault("voice", {})
            if "VOICE" in shim:
                voice["default"] = shim["VOICE"]
            if "VOICE_RATE" in shim:
                voice["rate"] = shim["VOICE_RATE"]
            if "VOICE_PITCH" in shim:
                voice["pitch"] = shim["VOICE_PITCH"]

    # Legacy TUI YAML — best-effort, optional PyYAML
    if LEGACY_TUI_CONFIG.exists():
        try:
            import yaml  # optional
            with open(LEGACY_TUI_CONFIG) as f:
                tui_legacy = yaml.safe_load(f) or {}
            merged["tui"] = tui_legacy
        except (ImportError, OSError, Exception):
            pass

    return merged


def load_config() -> dict:
    """Load config from canonical file. Migrate from legacy paths on first run."""
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

    # Canonical absent — perform one-shot migration from legacy paths
    merged = _migrate_legacy_configs()
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(merged, f, indent=2)
        import sys
        print(
            f"conductor: migrated config to {CONFIG_FILE}",
            file=sys.stderr,
        )
    except OSError:
        pass
    return merged


def save_config(config: dict) -> None:
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ═══════════════════════════════════════════════════════════════
# Profile resolution
# ═══════════════════════════════════════════════════════════════

def resolve_profile(name_or_cmd: str) -> dict:
    """
    Resolve a profile name to command + dir.

    If name matches a config profile, returns its settings.
    Otherwise treats the input as a raw command (backward compat).

    Returns:
        {"command": str, "dir": str|None}
    """
    config = load_config()
    profiles = config.get("profiles", {})
    default_dir = config.get("default_dir", "") or None

    if name_or_cmd in profiles:
        profile = profiles[name_or_cmd]
        return {
            "command": profile["command"],
            "dir": profile.get("dir") or default_dir,
        }

    # Not a profile name — treat as raw command
    return {
        "command": name_or_cmd,
        "dir": default_dir,
    }


# ═══════════════════════════════════════════════════════════════
# Voice allocation
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# Pane listing (pure; no MCP decorator)
# ═══════════════════════════════════════════════════════════════

def list_panes_core(session: Optional[str] = None) -> list[dict]:
    """
    List all panes in a session or current window. Pure helper used by
    _find_best_split and by the MCP/CLI list_panes wrappers.
    """
    args = [
        "tmux", "list-panes", "-F",
        "#{pane_id}|#{pane_index}|#{window_index}|#{pane_width}|#{pane_height}|"
        "#{pane_current_command}|#{pane_current_path}|#{pane_active}",
    ]

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
                "pane_id": pane_id,
                "pane_index": int(parts[1]),
                "window_index": int(parts[2]),
                "width": int(parts[3]),
                "height": int(parts[4]),
                "command": parts[5],
                "path": parts[6],
                "active": parts[7] == "1",
                "claude_status": status,
            })

    return panes


# ═══════════════════════════════════════════════════════════════
# Layout math
# ═══════════════════════════════════════════════════════════════

def _find_best_split(
    session: str,
    min_w: int,
    min_h: int,
    target_pane: Optional[str] = None,
) -> dict:
    """
    Decide where to place a new worker pane.

    Evaluates panes in the session and returns the best split action.
    Prefers horizontal splits (side-by-side), falls back to vertical,
    then new window if no pane can be split.

    Returns:
        {"action": "split_h"|"split_v"|"new_window", "target_pane": ..., "reason": ...}
    """
    panes = list_panes_core(session)
    if not panes:
        return {
            "action": "new_window",
            "target_pane": None,
            "reason": "No panes found in session",
        }

    # If target_pane specified, only evaluate that one
    if target_pane:
        candidates = [p for p in panes if p["pane_id"] == target_pane]
        if not candidates:
            return {
                "action": "new_window",
                "target_pane": None,
                "reason": f"Target pane {target_pane} not found",
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
                "reason": f"Horizontal split of {pane['pane_id']} ({w}x{h}) -> 2x({half_w}x{h})",
            }

        # Check vertical split (stacked): each half gets ~h/2
        half_h = h // 2
        if w >= min_w and half_h >= min_h:
            return {
                "action": "split_v",
                "target_pane": pane["pane_id"],
                "reason": f"Vertical split of {pane['pane_id']} ({w}x{h}) -> 2x({w}x{half_h})",
            }

    return {
        "action": "new_window",
        "target_pane": None,
        "reason": f"No pane large enough to split (need {min_w}x{min_h} per half)",
    }


# ═══════════════════════════════════════════════════════════════
# Context-percent readers
# ═══════════════════════════════════════════════════════════════

def _get_context_from_state_files(target: str) -> dict | None:
    """
    Try to get context percentage from state files written by the statusline script.

    Returns None if data unavailable or stale (>30 seconds old).
    """
    # First, get the pane ID for this target
    result = subprocess.run(
        ["tmux", "display-message", "-t", target, "-p", "#{pane_id}"],
        capture_output=True, text=True,
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
            "file_age_seconds": round(file_age, 1),
        }
    except (json.JSONDecodeError, IOError, KeyError):
        return None


def _get_context_from_terminal(target: str) -> dict:
    """
    Fallback: scrape context percentage from terminal status line.
    """
    # Capture the last few lines to find the status line
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", target, "-p", "-S", "-5"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return {
            "error": f"Failed to capture pane: {result.stderr.strip()}",
            "context_percent": None,
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
                "status": "ok",
            }

    return {
        "target": target,
        "context_percent": None,
        "source": "terminal_scrape",
        "raw_line": lines[-1] if lines else "",
        "status": "not_found",
        "hint": "Status line not visible - Claude may be processing or pane too small",
    }


# ═══════════════════════════════════════════════════════════════
# Speak (TTS) — shared by MCP speak tool and `cm speak` CLI verb
# ═══════════════════════════════════════════════════════════════

def speak_impl(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    volume: Optional[str] = None,
    worker_id: Optional[str] = None,
    blocking: bool = False,
    priority: bool = True,
) -> str:
    """
    Synchronous core implementation for TTS speech via edge-tts.

    Shared by the MCP `speak` tool (conductor.server) and the `cm speak` CLI
    verb (conductor.cli.speak). All voice/rate/pitch/volume resolution,
    cache management, audio-lock acquisition, and player dispatch happens
    here. Returns a short status message (same string the MCP tool returns)
    so callers can surface it verbatim.

    Args:
        text: Text to speak.
        voice: Edge TTS voice (defaults to config default, or worker's
            assigned voice when worker_id is set).
        rate: Speech rate override (e.g. "+20%"). Default from config.
        pitch: Pitch override (e.g. "+0Hz"). Default from config.
        volume: Volume override (e.g. "+0%"). Default from config.
        worker_id: If set and voice is None, uses the worker's unique voice.
        blocking: If True, block until playback finishes.
        priority: If True, wait up to 5s for the audio lock (direct calls
            take priority over fire-and-forget hook calls). If False and
            the lock is held, skip playback and return immediately.

    Returns:
        Short status string — "Speaking: ..." on success, or an error
        message on failure (gated / TTS failed / no player, etc.). Never
        raises for expected failures.
    """
    import fcntl

    config = load_config()

    # Gate: voice.enabled is the canonical on/off switch (cm-y7t). False
    # means no generation, no playback — mirrors state-tracker's guard.
    if not config["voice"].get("enabled", True):
        return "audio disabled (voice.enabled=false in config)"

    # Determine voice
    if voice is None:
        if worker_id:
            voice = get_worker_voice(worker_id)
        else:
            voice = config["voice"]["default"]

    # Determine rate / pitch / volume (CLI flags override config;
    # config falls back to per-key defaults if missing).
    if rate is None:
        rate = config["voice"]["rate"]
    if pitch is None:
        pitch = config["voice"].get("pitch", "+0Hz")
    if volume is None:
        volume = config["voice"].get("volume", "+0%")

    # Cache key includes all four knobs so changes invalidate properly.
    cache_key = hashlib.md5(
        f"{voice}:{rate}:{pitch}:{volume}:{text}".encode()
    ).hexdigest()
    cache_file = AUDIO_CACHE_DIR / f"{cache_key}.mp3"

    # Generate audio if not cached
    if not cache_file.exists():
        try:
            subprocess.run(
                [
                    "edge-tts", "--voice", voice, "--rate", rate,
                    "--pitch", pitch, "--volume", volume,
                    "--text", text, "--write-media", str(cache_file),
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            return (
                "TTS generation failed: "
                f"{e.stderr.decode() if e.stderr else str(e)}"
            )
        except FileNotFoundError:
            return "edge-tts not found. Install with: pip install edge-tts"

    # Acquire audio lock (priority=True waits briefly, False skips if busy)
    lock_fd = None
    try:
        lock_fd = open(AUDIO_LOCK_FILE, "w")
        if priority:
            # Wait up to 5 seconds for lock - direct calls take priority.
            acquired = False
            for _ in range(50):
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    time.sleep(0.1)
            # If we didn't acquire, proceed anyway for priority calls.
            _ = acquired
        else:
            # Non-blocking — skip if busy.
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "Audio busy, skipped"

        # Try multiple audio players in order of preference.
        players = [
            (["mpv", "--no-video", "--really-quiet", str(cache_file)], "mpv"),
            (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(cache_file)], "ffplay"),
            (["cvlc", "--play-and-exit", "--quiet", str(cache_file)], "vlc"),
        ]

        played = False
        for cmd, _name in players:
            try:
                if blocking or priority:
                    # Priority calls block to hold lock during playback.
                    subprocess.run(cmd, check=True, capture_output=True)
                else:
                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                played = True
                break
            except FileNotFoundError:
                continue

        if not played:
            return (
                f"Audio cached at {cache_file} - "
                "install mpv, ffplay, or vlc to play"
            )

    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass

    return f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}"


# ═══════════════════════════════════════════════════════════════
# Send keys (tmux) — shared by MCP send_keys tool and `cm send` CLI verb
# ═══════════════════════════════════════════════════════════════

def send_keys_impl(
    session: str,
    keys: str,
    submit: bool = True,
    delay_ms: int = DEFAULT_DELAY_MS,
) -> str:
    """
    Send keys to a tmux session. If submit=True, waits delay_ms then presses Enter.

    Synchronous helper shared by the MCP `send_keys` tool and the `cm send`
    CLI verb. The delay between text and Enter is critical for Claude/Codex —
    without it, they create a newline instead of submitting.

    Args:
        session: tmux session name or pane id.
        keys: Text/keys to send (literal, no tmux interpretation).
        submit: If True, wait delay_ms then press Enter (default: True).
        delay_ms: Milliseconds to wait before Enter (default: DEFAULT_DELAY_MS,
            ignored when submit=False).

    Returns:
        Short confirmation string matching the previous MCP return shape.
    """
    subprocess.run(
        ["tmux", "send-keys", "-t", session, "-l", keys],
        check=True,
    )

    if submit:
        time.sleep(delay_ms / 1000)
        subprocess.run(
            ["tmux", "send-keys", "-t", session, "Enter"],
            check=True,
        )
        return f"Sent keys to {session} ({len(keys)} chars, submitted after {delay_ms}ms)"

    return f"Sent keys to {session} ({len(keys)} chars, no submit)"


# ═══════════════════════════════════════════════════════════════
# Kill worker / pane — shared by MCP tools and `cm kill` CLI verbs
# ═══════════════════════════════════════════════════════════════

def kill_worker_impl(
    session: str,
    cleanup_worktree: bool = False,
    project_dir: Optional[str] = None,
) -> str:
    """
    Kill a worker's tmux session; optionally remove its git worktree.

    Shared by MCP `kill_worker` tool and `cm kill worker` CLI verb. Returns
    the same semicolon-joined status string the MCP tool returned.
    """
    messages: list[str] = []

    result = subprocess.run(
        ["tmux", "kill-session", "-t", session],
        capture_output=True, text=True,
    )

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
            from pathlib import Path as _Path
            project_path = _Path(project_dir).expanduser().resolve()
            worktree_path = project_path / ".worktrees" / session

            if worktree_path.exists():
                result = subprocess.run(
                    ["git", "-C", str(project_path), "worktree", "remove",
                     str(worktree_path), "--force"],
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    messages.append(f"Removed worktree: {worktree_path}")
                else:
                    messages.append(f"Failed to remove worktree: {result.stderr.strip()}")
            else:
                messages.append(f"Worktree not found: {worktree_path}")

    return "; ".join(messages)


def kill_pane_impl(pane_id: str) -> str:
    """
    Kill a specific tmux pane. Shared by MCP `kill_pane` and `cm kill pane`.

    Returns the same short confirmation string the MCP tool returned; an
    error message (prefixed "Failed to kill pane:") on failure.
    """
    result = subprocess.run(
        ["tmux", "kill-pane", "-t", pane_id],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return f"Failed to kill pane: {result.stderr.strip()}"

    return f"Killed pane: {pane_id}"


# ═══════════════════════════════════════════════════════════════
# Focus pane — shared by MCP focus_pane and `cm focus` CLI verb
# ═══════════════════════════════════════════════════════════════

def focus_pane_impl(pane_id: str) -> str:
    """
    Switch tmux focus to a specific pane. Shared by MCP and `cm focus`.

    Returns a short confirmation string; error message (prefixed
    "Failed to focus pane:") on failure.
    """
    result = subprocess.run(
        ["tmux", "select-pane", "-t", pane_id],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return f"Failed to focus pane: {result.stderr.strip()}"

    return f"Focused pane: {pane_id}"


# ═══════════════════════════════════════════════════════════════
# Popups — shared by MCP show_popup / show_status_popup and `cm popup ...`
# ═══════════════════════════════════════════════════════════════

def show_popup_impl(
    message: str,
    title: str = "Conductor",
    width: int = 50,
    height: int = 10,
    duration_s: int = 3,
    target: Optional[str] = None,
) -> str:
    """
    Show a floating tmux popup with `message`. Non-blocking (spawns Popen).

    Shared by MCP `show_popup` and `cm popup show`. Returns the same short
    confirmation string the MCP tool returned.
    """
    # Build the command to run inside popup
    escaped_msg = message.replace("'", "'\\''")
    popup_cmd = f"printf '%s\\n' '{escaped_msg}'; sleep {duration_s}"

    args = ["tmux", "display-popup"]

    if target:
        args.extend(["-t", target])

    args.extend([
        "-T", title,
        "-w", str(width),
        "-h", str(height),
        "-E", popup_cmd,
    ])

    # Run in background so it doesn't block
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return f"Popup shown: {message[:30]}{'...' if len(message) > 30 else ''}"


def _list_workers_core() -> list[dict]:
    """Return tmux sessions as worker dicts. Pure helper used by status popup."""
    result = subprocess.run(
        ["tmux", "list-sessions", "-F",
         "#{session_name}|#{session_created}|#{session_windows}|#{session_attached}"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return []

    workers: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            name = parts[0]
            status = None
            state_file = STATE_DIR / f"{name}.json"
            if state_file.exists():
                try:
                    with open(state_file) as f:
                        state = json.load(f)
                        status = state.get("status")
                except (json.JSONDecodeError, IOError):
                    pass

            workers.append({
                "session": name,
                "created": parts[1],
                "windows": int(parts[2]),
                "attached": parts[3] == "1",
                "claude_status": status,
            })

    return workers


def show_status_popup_impl(
    workers: Optional[list] = None,
    target: Optional[str] = None,
) -> str:
    """
    Show a popup with current worker status summary. Fetches fresh worker
    list when `workers` is None. Shared by MCP `show_status_popup` and
    `cm popup status`.
    """
    if workers is None:
        workers = _list_workers_core()

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

    return show_popup_impl(
        message=message,
        title="Worker Status",
        width=40,
        height=min(len(workers) + 6, 20),
        duration_s=5,
        target=target,
    )


# ═══════════════════════════════════════════════════════════════
# Session / window creation — shared by MCP tools and `cm session/window ...`
# ═══════════════════════════════════════════════════════════════

def create_session_impl(
    name: str,
    start_dir: Optional[str] = None,
    command: Optional[str] = None,
    attach: bool = False,
) -> dict:
    """
    Create a new tmux session. Shared by MCP `create_session` and
    `cm session new`. Returns a dict with session/window/pane ids on
    success, or {"error": "..."} on failure (matches prior MCP shape).
    """
    args = [
        "tmux", "new-session", "-s", name, "-P",
        "-F", "#{session_id}|#{window_id}|#{pane_id}",
    ]

    if not attach:
        args.append("-d")

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
        "attached": attach,
    }


def create_window_impl(
    session: str,
    name: Optional[str] = None,
    start_dir: Optional[str] = None,
    command: Optional[str] = None,
) -> dict:
    """
    Create a new window in an existing session. Shared by MCP
    `create_window` and `cm window new`. Matches prior MCP return shape;
    returns {"error": "..."} on tmux failure.
    """
    args = [
        "tmux", "new-window", "-t", f"{session}:", "-a", "-P",
        "-F", "#{window_id}|#{window_index}|#{pane_id}",
    ]

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
        "name": name,
    }


# ═══════════════════════════════════════════════════════════════
# Pane split / grid — shared by MCP split_pane / create_grid and CLI
# ═══════════════════════════════════════════════════════════════

def split_pane_impl(
    direction: str = "horizontal",
    target: Optional[str] = None,
    percentage: int = 50,
    start_dir: Optional[str] = None,
) -> dict:
    """
    Split the current or target pane. Shared by MCP `split_pane` and
    `cm split`. Matches prior MCP return shape; returns {"error": "..."}
    on tmux failure.

    Note: `percentage` is accepted for signature parity with the MCP tool
    but is currently unused (tmux's -p flag has issues in some versions;
    we rely on the default even split). Keeping the parameter means
    callers can upgrade when we revisit sizing.
    """
    args = ["tmux", "split-window"]

    if direction == "horizontal":
        args.append("-h")
    else:
        args.append("-v")

    if target:
        args.extend(["-t", target])

    if start_dir:
        args.extend(["-c", start_dir])

    args.extend(["-P", "-F", "#{pane_id}|#{pane_index}|#{pane_width}x#{pane_height}"])

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    parts = result.stdout.strip().split("|")
    return {
        "pane_id": parts[0] if len(parts) > 0 else None,
        "pane_index": int(parts[1]) if len(parts) > 1 else None,
        "size": parts[2] if len(parts) > 2 else None,
    }


def create_grid_impl(
    layout: str = "2x2",
    session: Optional[str] = None,
    start_dir: Optional[str] = None,
) -> dict:
    """
    Create a COLSxROWS grid of panes starting from the current pane.
    Shared by MCP `create_grid` and `cm grid`. Returns a dict with
    `layout`, `panes`, `count` on success, or `{"error": "..."}`.
    """
    try:
        cols, rows = map(int, layout.lower().split("x"))
    except ValueError:
        return {"error": f"Invalid layout format: {layout}. Use COLSxROWS (e.g., 2x2)"}

    total_panes = cols * rows
    if total_panes < 1 or total_panes > 16:
        return {"error": "Layout must create 1-16 panes"}

    target = f"{session}:" if session else ""

    result = subprocess.run(
        ["tmux", "display-message", "-t", target or ".", "-p", "#{pane_id}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {"error": "Could not get current pane"}

    first_pane = result.stdout.strip()
    panes = [first_pane]

    # Step 1: Create rows by vertical splits off the first pane
    current_pane = first_pane
    for _row in range(1, rows):
        split_result = split_pane_impl(
            direction="vertical",
            target=current_pane,
            start_dir=start_dir,
        )
        if "error" in split_result:
            return split_result
        panes.append(split_result["pane_id"])

    # Step 2: Split each row into columns
    row_panes = [first_pane] + [p for p in panes[1:]]

    final_panes: list[str] = []
    for _row_idx, row_pane in enumerate(row_panes[:rows]):
        row_result = [row_pane]
        current = row_pane

        for _col in range(1, cols):
            split_result = split_pane_impl(
                direction="horizontal",
                target=current,
                start_dir=start_dir,
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
        capture_output=True,
    )

    return {
        "layout": layout,
        "panes": final_panes[:total_panes],
        "count": len(final_panes[:total_panes]),
    }


# ═══════════════════════════════════════════════════════════════
# spawn_worker_in_pane — shared by MCP tool and `cm spawn in-pane`
# ═══════════════════════════════════════════════════════════════

def spawn_worker_in_pane_impl(
    pane_id: str,
    issue_id: str,
    project_dir: str,
    profile_cmd: str = "claude",
    inject_context: bool = True,
    boot_delay_s: float = 4.0,
    cd_delay_s: float = 0.3,
) -> dict:
    """
    Spawn a worker in an existing pane. Synchronous equivalent of the
    prior async MCP tool — the sleeps become blocking `time.sleep()`.

    Shared by MCP `spawn_worker_in_pane` and `cm spawn in-pane`.
    Returns a dict describing the spawn on success, or {"error": "..."}
    on failure to create the worktree.
    """
    project_path = Path(project_dir).expanduser().resolve()
    worktree_path = project_path / ".worktrees" / issue_id
    branch_name = f"feature/{issue_id}"

    # 1. Create worktree if needed
    if not worktree_path.exists():
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        branch_result = subprocess.run(
            ["git", "-C", str(project_path), "branch", "--list", branch_name],
            capture_output=True, text=True,
        )

        if branch_result.stdout.strip():
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 str(worktree_path), branch_name],
                check=True,
            )
        else:
            subprocess.run(
                ["git", "-C", str(project_path), "worktree", "add",
                 "-b", branch_name, str(worktree_path)],
                check=True,
            )

    # 2. cd into worktree in the pane
    subprocess.run(
        ["tmux", "send-keys", "-t", pane_id, f"cd {worktree_path}", "Enter"],
        check=True,
    )
    time.sleep(cd_delay_s)

    # 3. Launch agent
    subprocess.run(
        ["tmux", "send-keys", "-t", pane_id, profile_cmd, "Enter"],
        check=True,
    )

    # 4. Wait for agent to boot
    time.sleep(boot_delay_s)

    # 5. Inject beads context if requested
    context_text = ""
    if inject_context:
        try:
            bd_result = subprocess.run(
                ["bd", "show", issue_id, "--format", "json"],
                capture_output=True, text=True,
                cwd=str(project_path),
                env={**os.environ, "BEADS_WORKING_DIR": str(project_path)},
            )
            if bd_result.returncode == 0:
                issue = json.loads(bd_result.stdout)
                context_text = f"""Fix beads issue {issue_id}: "{issue.get('title', 'Unknown')}"

{issue.get('description', '')}

When done:
1. Run tests/build to verify
2. Commit your changes
3. Run: bd close {issue_id} --reason "Brief description of fix"
"""
        except Exception:
            context_text = f"Work on issue {issue_id}. When done: bd close {issue_id}"

    # 6. Send the context keys
    if context_text:
        send_keys_impl(pane_id, context_text)

    return {
        "pane_id": pane_id,
        "issue_id": issue_id,
        "worktree": str(worktree_path),
        "branch": branch_name,
        "context_injected": bool(context_text),
    }


# ═══════════════════════════════════════════════════════════════
# Resize / zoom / layout — shared by MCP tools and `cm resize/zoom/layout`
# ═══════════════════════════════════════════════════════════════

_RESIZE_ERROR_PREFIX = "Failed to resize:"
_ZOOM_ERROR_PREFIX = "Failed to toggle zoom:"
_LAYOUT_ERROR_PREFIX = "Failed to apply layout:"


def resize_pane_impl(
    pane_id: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    adjust_x: Optional[int] = None,
    adjust_y: Optional[int] = None,
) -> str:
    """
    Resize a pane. Shared by MCP `resize_pane` and `cm resize`. Returns
    a short confirmation, or error message prefixed "Failed to resize:".
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
        return f"{_RESIZE_ERROR_PREFIX} {result.stderr.strip()}"

    return f"Resized pane: {pane_id}"


def zoom_pane_impl(pane_id: str) -> str:
    """
    Toggle zoom (fullscreen) for a pane. Shared by MCP `zoom_pane` and
    `cm zoom`. Error messages are prefixed "Failed to toggle zoom:".
    """
    result = subprocess.run(
        ["tmux", "resize-pane", "-t", pane_id, "-Z"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return f"{_ZOOM_ERROR_PREFIX} {result.stderr.strip()}"

    return f"Toggled zoom for pane: {pane_id}"


_VALID_LAYOUTS = (
    "tiled", "even-horizontal", "even-vertical",
    "main-horizontal", "main-vertical",
)


def apply_layout_impl(
    layout: str,
    target: Optional[str] = None,
) -> str:
    """
    Apply a named tmux layout. Shared by MCP `apply_layout` and
    `cm layout apply`. Validates against the builtin list — returns
    a "Invalid layout..." string without shelling out on a typo.
    Tmux-level failures use the "Failed to apply layout:" prefix.
    """
    if layout not in _VALID_LAYOUTS:
        return f"Invalid layout. Valid options: {', '.join(_VALID_LAYOUTS)}"

    args = ["tmux", "select-layout"]

    if target:
        args.extend(["-t", target])

    args.append(layout)

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return f"{_LAYOUT_ERROR_PREFIX} {result.stderr.strip()}"

    return f"Applied layout: {layout}"


def rebalance_panes_impl(target: Optional[str] = None) -> str:
    """
    Rebalance panes to equal sizes via the tiled layout. Shared by MCP
    `rebalance_panes` and `cm layout rebalance`. Returns a confirmation
    string with the pane count or propagates apply_layout's error string.
    """
    args = ["tmux", "list-panes"]
    if target:
        args.extend(["-t", target])

    result = subprocess.run(args, capture_output=True, text=True)
    pane_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    apply_result = apply_layout_impl("tiled", target)

    if "Failed" in apply_result or apply_result.startswith("Invalid layout"):
        return apply_result

    return f"Rebalanced {pane_count} panes with tiled layout"


# ═══════════════════════════════════════════════════════════════
# WATCH / HOOK / CONFIG IMPLs (cm-aax.7)
# ═══════════════════════════════════════════════════════════════


def watch_pane_impl(
    pane_id: str,
    output_file: Optional[str] = None,
) -> dict:
    """
    Start streaming a pane's output to a file via tmux pipe-pane. Shared by
    MCP `watch_pane` and `cm watch start`.

    Returns {"pane_id", "output_file", "status": "watching"} on success or
    {"error": str} on tmux failure. Default output path is
    ``WATCH_DIR/pane-<id>.log`` (with `%` stripped from pane_id for FS safety).
    """
    if output_file is None:
        safe_id = pane_id.replace("%", "pane-")
        output_file = str(WATCH_DIR / f"{safe_id}.log")

    # Ensure output file exists and is empty
    Path(output_file).write_text("")

    result = subprocess.run(
        ["tmux", "pipe-pane", "-t", pane_id, f"cat >> {output_file}"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    return {
        "pane_id": pane_id,
        "output_file": output_file,
        "status": "watching",
    }


def stop_watch_impl(pane_id: str) -> str:
    """
    Stop streaming a pane's output. Shared by MCP `stop_watch` and
    `cm watch stop`. Error strings are prefixed "Failed to stop watch:".
    """
    result = subprocess.run(
        ["tmux", "pipe-pane", "-t", pane_id],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        return f"Failed to stop watch: {result.stderr.strip()}"

    return f"Stopped watching pane: {pane_id}"


def read_watch_impl(
    pane_id: str,
    lines: int = 50,
    output_file: Optional[str] = None,
) -> str:
    """
    Read recent output from a watched pane's log file. Shared by MCP
    `read_watch` and `cm watch read`.

    Returns last N lines joined with newlines, or a human-readable error
    string when no watch file exists or the read fails.
    """
    if output_file is None:
        safe_id = pane_id.replace("%", "pane-")
        output_file = str(WATCH_DIR / f"{safe_id}.log")

    path = Path(output_file)
    if not path.exists():
        return f"No watch file found for {pane_id}. Start with watch_pane() first."

    try:
        content = path.read_text()
        all_lines = content.splitlines()
        return "\n".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading watch file: {e}"


_VALID_HOOK_EVENTS = (
    "pane-died", "pane-exited", "pane-focus-in", "pane-focus-out",
    "pane-mode-changed", "pane-set-clipboard",
)


def set_pane_hook_impl(
    event: str,
    command: str,
    session: Optional[str] = None,
) -> str:
    """
    Register a tmux hook. Shared by MCP `set_pane_hook` and `cm hook set`.

    `session=None` installs the hook globally (`tmux set-hook -g`); pass a
    session name to scope it (`tmux set-hook -t <session>`). Rejects unknown
    events with a human-readable message (no tmux call) to surface typos
    early. Error strings are prefixed "Failed to set hook:".
    """
    if event not in _VALID_HOOK_EVENTS:
        return f"Invalid event. Valid events: {', '.join(_VALID_HOOK_EVENTS)}"

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


def clear_hook_impl(
    event: str,
    session: Optional[str] = None,
) -> str:
    """
    Clear a previously set tmux hook. Shared by MCP `clear_hook` and
    `cm hook clear`. Error strings are prefixed "Failed to clear hook:".
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


def list_hooks_impl(session: Optional[str] = None) -> list[dict]:
    """
    List registered tmux hooks. Shared by MCP `list_hooks` and
    `cm hook list`. Returns [] on tmux error or no hooks.

    Each record has keys {"event", "command"}. The scoping target
    (session or global) is the caller's responsibility to remember —
    tmux `show-hooks` does not echo it back.
    """
    args = ["tmux", "show-hooks"]

    if session:
        args.extend(["-t", session])
    else:
        args.append("-g")

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode != 0:
        return []

    hooks: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Format: "event command"
        parts = line.split(" ", 1)
        if len(parts) >= 2:
            hooks.append({
                "event": parts[0],
                "command": parts[1],
            })

    return hooks


def get_config_impl() -> dict:
    """
    Return the full conductor config dict. Shared by MCP `get_config` and
    `cm config get`. Thin passthrough to `load_config()` — kept as a
    distinct name so the cm-aax.5/.6/.7 ``*_impl`` convention holds.
    """
    return load_config()
