"""cm session — tmux-session verbs.

Migrated as part of cm-aax.6. `cm session new` mirrors the MCP
`create_session` tool; both call `conductor.core.create_session_impl()`.

The sub-group anticipates future sibling verbs (`cm session list`,
`cm session attach`, ...) without changing the CLI surface.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json, emit_tsv


_SESSION_NEW_FIELDS = [
    "session", "session_id", "window_id", "pane_id", "attached",
]


@cli.group(
    "session",
    help="Manage tmux sessions. Sub-commands: new (create a session).",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def session_group() -> None:
    """Parent group for all `cm session ...` verbs."""


@session_group.command(
    "new",
    help=(
        "Create a new tmux session NAME. Detached by default (pass "
        "--attach to attach). Use --cwd to set the initial working "
        "directory and --command to launch a non-shell command."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("name")
@click.option(
    "--cwd",
    "start_dir",
    default=None,
    help="Working directory (default: current).",
)
@click.option(
    "--command",
    default=None,
    help="Command to run in initial window (default: shell).",
)
@click.option(
    "--attach",
    is_flag=True,
    default=False,
    help="Attach to the new session instead of detaching.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit single-line JSON instead of TSV.",
)
def session_new_cmd(
    name: str,
    start_dir: str | None,
    command: str | None,
    attach: bool,
    as_json: bool,
) -> None:
    """Implementation of `cm session new`."""
    from conductor.core import create_session_impl

    try:
        result = create_session_impl(
            name,
            start_dir=start_dir,
            command=command,
            attach=attach,
        )
    except Exception as exc:
        msg = f"session new failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"session new failed: {result['error']}")
        return

    if as_json:
        emit_json(result)
        return

    emit_tsv([result], _SESSION_NEW_FIELDS)


__all__ = ["session_group", "session_new_cmd"]
