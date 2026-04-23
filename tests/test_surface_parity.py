"""Surface-parity tests — every shared verb exists on both MCP and CLI.

Run with: `uv run pytest tests/test_surface_parity.py -v`.

## Why this file exists

The `cm` CLI and the `conductor-mcp` MCP server are two agent-facing
surfaces over the same core. The CLI-vs-MCP policy in CLAUDE.md (cm-aax)
picks a single *home* for each verb based on call frequency / payload,
BUT a handful of verbs must live on both surfaces (for instance when a
scripted pipeline and an interactive agent both care about `speak`).

This test locks that list — `SHARED_SURFACE` — and asserts every name is
reachable on both sides. Rename either registration, or forget to add the
CLI mirror, and the test goes red.

## Naming convention (mirrors conductor/cli/__init__.py)

MCP tool names are flat snake_case: `speak`, `list_hooks`, `list_panes`.
The CLI may expose the same verbs as:

1. Flat, matching MCP exactly: `cm speak` (MCP `speak`).
2. Grouped `<noun> <verb>` when the noun has ≥2 related verbs:
   `list_hooks` → `cm hook list`, `list_panes` → `cm pane list`,
   `set_pane_hook` → `cm hook set`.

When a CLI path differs from the MCP name, register the mapping in
`CLI_PATH_MAP` below. Empty for the cm-aax.3 landing (only `speak`, which
is flat on both sides) — migrations in cm-aax.5/.6/.7 will grow it.
"""

from __future__ import annotations

import asyncio

import click
import pytest


# ─── The shared surface ─────────────────────────────────────────
# Grow this list as cm-aax.5/.6/.7 migrate verbs that need to live on
# both sides. Most verbs will be CLI-only (the MCP footprint shrinks by
# design) and so won't appear here.
SHARED_SURFACE: list[str] = [
    "speak",
    "send_keys",
    "kill_worker",
    "kill_pane",
    "focus_pane",
    "show_popup",
    "show_status_popup",
]

# MCP name -> CLI path (space-separated). Missing entries mean the CLI
# path is identical to the MCP name (flat). Example once migrations land:
#   "list_hooks": "hook list",
#   "set_pane_hook": "hook set",
CLI_PATH_MAP: dict[str, str] = {
    "send_keys": "send",
    "kill_worker": "kill worker",
    "kill_pane": "kill pane",
    "focus_pane": "focus",
    "show_popup": "popup show",
    "show_status_popup": "popup status",
}


# ─── Helpers ────────────────────────────────────────────────────

def _mcp_tool_names() -> set[str]:
    """Collect all MCP tool names registered on the FastMCP server."""
    from conductor.server import mcp

    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def _walk_cli(group: click.Group, prefix: str = "") -> set[str]:
    """Recursively collect all CLI command paths under a click Group.

    Returns a set of space-separated paths, e.g. {"speak", "hook list"}.
    """
    paths: set[str] = set()
    for name, cmd in group.commands.items():
        path = f"{prefix}{name}" if not prefix else f"{prefix} {name}"
        if isinstance(cmd, click.Group):
            paths |= _walk_cli(cmd, prefix=path)
        else:
            paths.add(path)
    return paths


def _cli_paths() -> set[str]:
    """Collect all CLI command paths from the `cm` group."""
    from conductor.cli import cli

    return _walk_cli(cli)


def _resolve_cli_path(mcp_name: str) -> str:
    """Resolve an MCP tool name to its expected CLI path via CLI_PATH_MAP.

    Defaults to the flat name (identical to MCP).
    """
    return CLI_PATH_MAP.get(mcp_name, mcp_name)


# ─── Tests ──────────────────────────────────────────────────────

def test_mcp_has_all_shared() -> None:
    """Every name in SHARED_SURFACE must exist as an MCP tool."""
    mcp_names = _mcp_tool_names()
    missing = [name for name in SHARED_SURFACE if name not in mcp_names]
    assert not missing, (
        f"Missing MCP tools for shared surface: {missing}. "
        f"Got MCP tools: {sorted(mcp_names)}"
    )


def test_cli_has_all_shared() -> None:
    """Every name in SHARED_SURFACE must exist as a CLI command path."""
    cli_paths = _cli_paths()
    missing = []
    for mcp_name in SHARED_SURFACE:
        path = _resolve_cli_path(mcp_name)
        if path not in cli_paths:
            missing.append((mcp_name, path))
    assert not missing, (
        f"Missing CLI paths for shared surface: {missing}. "
        f"Got CLI paths: {sorted(cli_paths)}"
    )


def test_cli_path_map_targets_exist() -> None:
    """Every CLI_PATH_MAP target must exist in the CLI command tree.

    Catches stale mappings left over when a CLI path is renamed but the
    map isn't updated.
    """
    if not CLI_PATH_MAP:
        pytest.skip("CLI_PATH_MAP is empty (no grouped verbs yet)")

    cli_paths = _cli_paths()
    bad = [
        (mcp_name, path)
        for mcp_name, path in CLI_PATH_MAP.items()
        if path not in cli_paths
    ]
    assert not bad, f"CLI_PATH_MAP points at non-existent paths: {bad}"
