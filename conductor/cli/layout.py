"""cm layout — tmux-layout verbs (`apply`, `rebalance`).

Migrated as part of cm-aax.6. `cm layout apply` mirrors the MCP
`apply_layout` tool, `cm layout rebalance` mirrors `rebalance_panes`.
Both call into `conductor.core` (`apply_layout_impl`,
`rebalance_panes_impl`).

Fire-and-forget: silent on success by default, `{"ok": true}` on --json.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json


# Must stay in sync with conductor.core._LAYOUT_ERROR_PREFIX.
_LAYOUT_ERROR_PREFIX = "Failed to apply layout:"
_INVALID_LAYOUT_PREFIX = "Invalid layout"


@cli.group(
    "layout",
    help=(
        "Manage tmux layouts. Sub-commands: apply (select a named "
        "layout), rebalance (redistribute panes evenly)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def layout_group() -> None:
    """Parent group for all `cm layout ...` verbs."""


@layout_group.command(
    "apply",
    short_help="Apply a named tmux layout.",
    help=(
        "Apply a named tmux layout to the current window. NAME is one of: "
        "tiled, even-horizontal, even-vertical, main-horizontal, main-vertical."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("name")
@click.option(
    "--target",
    default=None,
    help="Target window (default: current).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def layout_apply_cmd(name: str, target: str | None, as_json: bool) -> None:
    """Implementation of `cm layout apply`."""
    from conductor.core import apply_layout_impl

    try:
        result = apply_layout_impl(name, target=target)
    except Exception as exc:
        msg = f"layout apply failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_LAYOUT_ERROR_PREFIX) or result.startswith(_INVALID_LAYOUT_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@layout_group.command(
    "rebalance",
    short_help="Rebalance panes to equal sizes.",
    help=(
        "Rebalance the current window's panes to equal sizes (tiled). "
        "Useful after killing a pane."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--target",
    default=None,
    help="Target window (default: current).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def layout_rebalance_cmd(target: str | None, as_json: bool) -> None:
    """Implementation of `cm layout rebalance`."""
    from conductor.core import rebalance_panes_impl

    try:
        result = rebalance_panes_impl(target=target)
    except Exception as exc:
        msg = f"layout rebalance failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_LAYOUT_ERROR_PREFIX) or result.startswith(_INVALID_LAYOUT_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


__all__ = ["layout_group", "layout_apply_cmd", "layout_rebalance_cmd"]
