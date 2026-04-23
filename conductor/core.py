"""conductor.core — pure helpers shared by MCP server and CLI.

No MCP decorators here, no click decorators here. Just tmux calls, config
parsing, voice allocation, layout math, and state-file readers. Both the
server and the CLI import from this module.
"""

from __future__ import annotations

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
