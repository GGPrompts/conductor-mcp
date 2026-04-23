"""cm grid — create a COLSxROWS grid of tmux panes.

Migrated as part of cm-aax.6. Mirrors the MCP `create_grid` tool; both
call `conductor.core.create_grid_impl()`.

TSV output (default) emits one pane id per line (`<pane_id>` column).
`--json` emits the same dict the MCP tool returned on a single line.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json, emit_tsv


@cli.command(
    "grid",
    short_help="Create a COLSxROWS grid of panes.",
    help=(
        "Create a COLSxROWS grid of panes (e.g. 2x2, 3x1, 4x1). Starts "
        "from the current pane and splits to fill the layout. Default "
        "TSV output is one pane_id per line in grid order."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("layout")
@click.option(
    "--target",
    "session",
    default=None,
    help="Target session (default: current).",
)
@click.option(
    "--start-dir",
    default=None,
    help="Working directory for all panes (default: inherit).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit single-line JSON instead of TSV.",
)
def grid_cmd(
    layout: str,
    session: str | None,
    start_dir: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm grid`."""
    from conductor.core import create_grid_impl

    try:
        result = create_grid_impl(
            layout=layout,
            session=session,
            start_dir=start_dir,
        )
    except Exception as exc:
        msg = f"grid failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"grid failed: {result['error']}")
        return

    if as_json:
        emit_json(result)
        return

    # TSV: one pane_id per line so `cm grid 2x2 | xargs -I{} cm focus {}`
    # works naturally.
    records = [{"pane_id": pid} for pid in result.get("panes", [])]
    emit_tsv(records, ["pane_id"])


__all__ = ["grid_cmd"]
