"""cm window — tmux-window verbs.

Migrated as part of cm-aax.6. `cm window new` mirrors the MCP
`create_window` tool; both call `conductor.core.create_window_impl()`.

The sub-group anticipates future sibling verbs (`cm window list`, ...).
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json, emit_tsv


_WINDOW_NEW_FIELDS = ["session", "window_id", "window_index", "pane_id", "name"]


@cli.group(
    "window",
    help="Manage tmux windows. Sub-commands: new (create a window).",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def window_group() -> None:
    """Parent group for all `cm window ...` verbs."""


@window_group.command(
    "new",
    help=(
        "Create a new window in SESSION. Use --name to label the window, "
        "--cwd to set the working directory, --command to launch a "
        "non-shell command."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("session")
@click.option(
    "--name",
    default=None,
    help="Window name.",
)
@click.option(
    "--cwd",
    "start_dir",
    default=None,
    help="Working directory (default: inherit from session).",
)
@click.option(
    "--command",
    default=None,
    help="Command to run (default: shell).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit single-line JSON instead of TSV.",
)
def window_new_cmd(
    session: str,
    name: str | None,
    start_dir: str | None,
    command: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm window new`."""
    from conductor.core import create_window_impl

    try:
        result = create_window_impl(
            session,
            name=name,
            start_dir=start_dir,
            command=command,
        )
    except Exception as exc:
        msg = f"window new failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"window new failed: {result['error']}")
        return

    if as_json:
        emit_json(result)
        return

    emit_tsv([result], _WINDOW_NEW_FIELDS)


__all__ = ["window_group", "window_new_cmd"]
