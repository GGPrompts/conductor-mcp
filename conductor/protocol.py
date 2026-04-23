"""conductor.protocol — shared return-shape types for MCP + CLI surfaces.

TypedDicts (not pydantic) to keep runtime overhead zero and avoid adding a
pydantic dependency. These mirror the exact shapes returned by today's MCP
tools so that CLI JSON output can match them field-for-field. Do not change
these shapes without updating both the MCP tool docstrings and the CLI
--json output paths.

Source-of-truth mapping to MCP tools in conductor.server:
- WorkerInfo     ← list_workers[*]
- PaneInfo       ← list_panes[*]
- WorkerStatus   ← get_worker_status (state-file JSON; shape defined by the
                   state-tracker hook, not by us, so kept loose)
- SpawnResult    ← spawn_worker / spawn_worker_in_pane / smart_spawn
- HookInfo       ← list_hooks[*]
- ContextPercent ← get_context_percent
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class WorkerInfo(TypedDict, total=False):
    """One item returned by list_workers()."""
    session: str
    created: str
    windows: int
    attached: bool
    claude_status: Optional[str]


class PaneInfo(TypedDict, total=False):
    """One item returned by list_panes()."""
    pane_id: str
    pane_index: int
    window_index: int
    width: int
    height: int
    command: str
    path: str
    active: bool
    claude_status: Optional[str]


class WorkerStatus(TypedDict, total=False):
    """Shape of /tmp/claude-code-state/{session}.json as consumed by
    get_worker_status(). The state-tracker hook owns this schema; we keep
    it loose on purpose so changes there don't require a protocol bump."""
    status: Optional[str]
    claude_session_id: Optional[str]
    # Additional fields passed through from state-tracker hook.


class Placement(TypedDict, total=False):
    """Placement decision embedded in SpawnResult (from _find_best_split)."""
    action: str  # "split_h" | "split_v" | "new_window"
    target_pane: Optional[str]
    reason: str


class SpawnResult(TypedDict, total=False):
    """Unified shape for spawn_worker / spawn_worker_in_pane / smart_spawn
    results. Not every field is present for every spawner — use .get()."""
    session: str
    pane_id: str
    issue_id: str
    worktree: str
    branch: str
    context_injected: bool
    placement: Placement
    profile: str
    error: str


class HookInfo(TypedDict, total=False):
    """One item returned by list_hooks()."""
    event: str
    command: str


class ContextPercent(TypedDict, total=False):
    """Shape returned by get_context_percent(). Two sources: state_file
    (preferred) and terminal_scrape (fallback); they carry different extra
    fields so only the common core is required."""
    target: str
    context_percent: Optional[int]
    source: str  # "state_file" | "terminal_scrape"
    status: str  # "ok" | "not_found"
    # state_file extras
    context_window_size: Optional[int]
    total_input_tokens: Optional[int]
    total_output_tokens: Optional[int]
    file_age_seconds: Optional[float]
    # terminal_scrape extras
    raw_line: str
    hint: str
    # common on failure
    error: str


# Re-export for ergonomic `from conductor.protocol import *` use.
__all__ = [
    "WorkerInfo",
    "PaneInfo",
    "WorkerStatus",
    "Placement",
    "SpawnResult",
    "HookInfo",
    "ContextPercent",
]
