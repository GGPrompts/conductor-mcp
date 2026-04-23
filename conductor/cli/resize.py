"""cm resize — resize a tmux pane.

Migrated as part of cm-aax.6. Mirrors the MCP `resize_pane` tool; both
call `conductor.core.resize_pane_impl()`.

CLI flags mirror tmux's own `resize-pane` flags so muscle-memory
transfers: -x/-y for absolute dimensions, -R/-L/-D/-U for relative
adjustments. All counts are positive integers (direction is implied by
the flag). Multiple flags combine.

Fire-and-forget: silent on success by default, `{"ok": true}` on --json.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json


# Must stay in sync with conductor.core._RESIZE_ERROR_PREFIX.
_ERROR_PREFIX = "Failed to resize:"


@cli.command(
    "resize",
    help=(
        "Resize tmux pane PANE_ID. Pass absolute dimensions with -x/-y "
        "or relative adjustments with -R/-L/-D/-U (values positive). "
        "Flags mirror tmux(1) resize-pane."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane_id")
@click.option(
    "-x", "--width",
    type=int,
    default=None,
    help="Absolute width in columns.",
)
@click.option(
    "-y", "--height",
    type=int,
    default=None,
    help="Absolute height in rows.",
)
@click.option(
    "-R", "--right",
    "right",
    type=int,
    default=None,
    help="Grow width to the right by N columns.",
)
@click.option(
    "-L", "--left",
    "left",
    type=int,
    default=None,
    help="Grow width to the left by N columns.",
)
@click.option(
    "-D", "--down",
    "down",
    type=int,
    default=None,
    help="Grow height downward by N rows.",
)
@click.option(
    "-U", "--up",
    "up",
    type=int,
    default=None,
    help="Grow height upward by N rows.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def resize_cmd(
    pane_id: str,
    width: int | None,
    height: int | None,
    right: int | None,
    left: int | None,
    down: int | None,
    up: int | None,
    as_json: bool,
) -> None:
    """Implementation of `cm resize`."""
    # Map directional flags onto the impl's adjust_x / adjust_y signs:
    # +adjust_x -> -R, -adjust_x -> -L; +adjust_y -> -D, -adjust_y -> -U.
    if right is not None and left is not None:
        die("resize: pass at most one of -R / -L")
        return
    if down is not None and up is not None:
        die("resize: pass at most one of -D / -U")
        return

    adjust_x: int | None = None
    if right is not None:
        adjust_x = right
    elif left is not None:
        adjust_x = -left

    adjust_y: int | None = None
    if down is not None:
        adjust_y = down
    elif up is not None:
        adjust_y = -up

    from conductor.core import resize_pane_impl

    try:
        result = resize_pane_impl(
            pane_id,
            width=width,
            height=height,
            adjust_x=adjust_x,
            adjust_y=adjust_y,
        )
    except Exception as exc:
        msg = f"resize failed: {exc}"
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


__all__ = ["resize_cmd"]
