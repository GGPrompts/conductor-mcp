"""cm list — list tmux workers (`workers`) and panes (`panes`).

Migrated as part of cm-aax.9 (polling migration). Wraps the pure helpers
in `conductor.core` (`list_workers_impl`, `list_panes_impl`) — the same
helpers the MCP tools `list_workers` / `list_panes` call, so the return
shape matches `conductor.protocol.WorkerInfo` / `PaneInfo` field-for-field.

## Output shapes

Both subcommands emit terse TSV by default (no header, one record per
line, stable column order) and `--json` for the raw list. Empty result
sets write nothing to stdout — silent success, matching the contract
in `conductor.cli._output`.

TSV column order (documented here for scripts pulling fields with `cut`):

- `cm list workers`: session<TAB>created<TAB>windows<TAB>attached<TAB>claude_status
- `cm list panes`:   pane_id<TAB>pane_index<TAB>window_index<TAB>width<TAB>height<TAB>command<TAB>path<TAB>active<TAB>claude_status
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit, emit_json
from conductor.core import list_panes_impl, list_workers_impl


_WORKER_FIELDS = ["session", "created", "windows", "attached", "claude_status"]
_PANE_FIELDS = [
    "pane_id",
    "pane_index",
    "window_index",
    "width",
    "height",
    "command",
    "path",
    "active",
    "claude_status",
]


@cli.group(
    "list",
    help=(
        "List tmux state. Sub-commands: workers (active sessions), "
        "panes (panes in a session / current window)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def list_group() -> None:
    """Parent group for all `cm list ...` verbs."""


@list_group.command(
    "workers",
    short_help="List active worker sessions.",
    help=(
        "List active tmux sessions that look like workers. Default TSV "
        "columns: session<TAB>created<TAB>windows<TAB>attached<TAB>claude_status. "
        "Use --json for the raw list."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit [{session, created, windows, attached, claude_status}, ...] as single-line JSON.",
)
def list_workers_cmd(as_json: bool) -> None:
    """Implementation of `cm list workers`."""
    try:
        workers = list_workers_impl()
    except Exception as exc:
        msg = f"list workers failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    emit(workers, json=as_json, fields=_WORKER_FIELDS)


@list_group.command(
    "panes",
    short_help="List panes in a session.",
    help=(
        "List panes in SESSION (or the current session if omitted). "
        "Default TSV columns: "
        "pane_id<TAB>pane_index<TAB>window_index<TAB>width<TAB>height"
        "<TAB>command<TAB>path<TAB>active<TAB>claude_status. "
        "Use --json for the raw list."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--session",
    default=None,
    help="Session to list (default: current session, all windows).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full list as single-line JSON.",
)
def list_panes_cmd(session: str | None, as_json: bool) -> None:
    """Implementation of `cm list panes`."""
    try:
        panes = list_panes_impl(session)
    except Exception as exc:
        msg = f"list panes failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    emit(panes, json=as_json, fields=_PANE_FIELDS)


__all__ = ["list_group", "list_workers_cmd", "list_panes_cmd"]
