"""cm zoom — toggle fullscreen zoom on a tmux pane.

Migrated as part of cm-aax.6. Mirrors the MCP `zoom_pane` tool; both
call `conductor.core.zoom_pane_impl()`.

Fire-and-forget: silent on success by default, `{"ok": true}` on --json.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json


# Must stay in sync with conductor.core._ZOOM_ERROR_PREFIX.
_ERROR_PREFIX = "Failed to toggle zoom:"


@cli.command(
    "zoom",
    short_help="Toggle fullscreen zoom on a pane.",
    help="Toggle fullscreen zoom on tmux pane PANE_ID (call again to unzoom).",
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
def zoom_cmd(pane_id: str, as_json: bool) -> None:
    """Implementation of `cm zoom`."""
    from conductor.core import zoom_pane_impl

    try:
        result = zoom_pane_impl(pane_id)
    except Exception as exc:
        msg = f"zoom failed: {exc}"
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


__all__ = ["zoom_cmd"]
