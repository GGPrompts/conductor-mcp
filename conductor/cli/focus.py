"""cm focus — switch tmux focus to a specific pane.

Migrated as part of cm-aax.5. Mirrors the MCP `focus_pane` tool; both
call `conductor.core.focus_pane_impl()`.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import focus_pane_impl


_ERROR_PREFIX = "Failed to focus pane:"


@cli.command(
    "focus",
    help="Switch tmux focus to PANE_ID (e.g. %0, %5).",
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
def focus_cmd(pane_id: str, as_json: bool) -> None:
    """Implementation of `cm focus`."""
    try:
        result = focus_pane_impl(pane_id)
    except Exception as exc:
        msg = f"focus failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_ERROR_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


__all__ = ["focus_cmd"]
