"""cm kill — kill tmux sessions (`worker`) or individual panes (`pane`).

Migrated as part of cm-aax.5. Uses a click sub-group so related "kill"
verbs compose into one coherent command surface — `cm kill worker`,
`cm kill pane`, and future siblings. Each subcommand is a thin wrapper
around a `*_impl` helper in `conductor.core`.

The MCP tools `kill_worker` / `kill_pane` stay registered unchanged and
call the same helpers, so surface parity is preserved.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import kill_pane_impl, kill_worker_impl


# Known failure prefixes in the helpers' return strings. Matching these
# lets the CLI distinguish "no-op success" (session not found) from real
# errors for the purpose of exit code + --json shape.
_PANE_ERROR_PREFIX = "Failed to kill pane:"


@cli.group(
    "kill",
    help=(
        "Terminate workers or panes. Sub-commands: worker (kill a tmux "
        "session), pane (kill an individual pane by id)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def kill_group() -> None:
    """Parent group for all `cm kill ...` verbs."""


@kill_group.command(
    "worker",
    help=(
        "Kill the tmux session SESSION and remove any state file. "
        "Pass --cleanup-worktree (with --project-dir) to also remove "
        "the git worktree at <project-dir>/.worktrees/<session>."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("session")
@click.option(
    "--cleanup-worktree",
    is_flag=True,
    default=False,
    help="Also remove the git worktree for this worker.",
)
@click.option(
    "--project-dir",
    default=None,
    help="Project directory (required with --cleanup-worktree).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true, \"message\": ...} as single-line JSON.",
)
def kill_worker_cmd(
    session: str,
    cleanup_worktree: bool,
    project_dir: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm kill worker`."""
    try:
        message = kill_worker_impl(
            session,
            cleanup_worktree=cleanup_worktree,
            project_dir=project_dir,
        )
    except Exception as exc:
        msg = f"kill worker failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json({"ok": True, "message": message})
        return
    # Default TSV mode: silent on success. The impl's return string is a
    # semicolon-joined status log useful interactively; scripts can use --json.
    return


@kill_group.command(
    "pane",
    help="Kill tmux pane PANE_ID (e.g. %0, %5).",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane_id")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def kill_pane_cmd(pane_id: str, as_json: bool) -> None:
    """Implementation of `cm kill pane`."""
    try:
        result = kill_pane_impl(pane_id)
    except Exception as exc:
        msg = f"kill pane failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_PANE_ERROR_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


__all__ = ["kill_group", "kill_worker_cmd", "kill_pane_cmd"]
