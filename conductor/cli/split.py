"""cm split — split a tmux pane to create a new one.

Migrated as part of cm-aax.6. Mirrors the MCP `split_pane` tool; both
call `conductor.core.split_pane_impl()`.

TSV output (default) is a single line: `<pane_id>\t<pane_index>\t<size>`.
`--json` emits the same shape as the MCP tool (dict) on one line.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json, emit_tsv


_SPLIT_FIELDS = ["pane_id", "pane_index", "size"]


@cli.command(
    "split",
    help=(
        "Split a pane. Default is horizontal (side-by-side). Use -v for "
        "vertical (stacked). TARGET defaults to the current pane."
    ),
    context_settings={"help_option_names": ["--help"]},
)
@click.option(
    "-h", "--horizontal",
    "horizontal",
    is_flag=True,
    default=False,
    help="Horizontal split — side by side (default).",
)
@click.option(
    "-v", "--vertical",
    "vertical",
    is_flag=True,
    default=False,
    help="Vertical split — stacked.",
)
@click.option(
    "--target",
    default=None,
    help="Target pane id (e.g. %0). Default: current pane.",
)
@click.option(
    "--size",
    "size",
    type=int,
    default=50,
    show_default=True,
    help="Size of new pane as percentage (reserved; tmux even-split currently).",
)
@click.option(
    "--start-dir",
    default=None,
    help="Working directory for the new pane (default: inherit).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit single-line JSON instead of TSV.",
)
def split_cmd(
    horizontal: bool,
    vertical: bool,
    target: str | None,
    size: int,
    start_dir: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm split`."""
    if horizontal and vertical:
        die("split: pass at most one of -h / -v")
        return

    direction = "vertical" if vertical else "horizontal"

    from conductor.core import split_pane_impl

    try:
        result = split_pane_impl(
            direction=direction,
            target=target,
            percentage=size,
            start_dir=start_dir,
        )
    except Exception as exc:
        msg = f"split failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"split failed: {result['error']}")
        return

    if as_json:
        emit_json(result)
        return

    emit_tsv([result], _SPLIT_FIELDS)


__all__ = ["split_cmd"]
