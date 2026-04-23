"""cm context — read Claude Code's context % for a tmux target.

Migrated as part of cm-aax.9 (polling migration). Wraps
`conductor.core.get_context_percent_impl()` — the same helper the MCP
`get_context_percent` tool calls. Return shape matches
`conductor.protocol.ContextPercent`.

## Output shapes

Default TSV emits a single line with the stable column order:
target<TAB>context_percent<TAB>source<TAB>status — terse enough to be
polled cheaply from shell scripts (`cm context BD-abc | cut -f2`).
Use `--json` for the full dict (context_window_size, token counts,
raw_line, hint, etc. depending on source).
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit, emit_json
from conductor.core import get_context_percent_impl


_CONTEXT_FIELDS = ["target", "context_percent", "source", "status"]


@cli.command(
    "context",
    short_help="Read Claude's context % for a target.",
    help=(
        "Print the context usage % for TARGET (tmux session name or "
        "pane id). Prefers the state-file source; falls back to scraping "
        "the visible terminal status line. Default TSV columns: "
        "target<TAB>context_percent<TAB>source<TAB>status. "
        "Use --json for the full dict."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("target")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full context dict as single-line JSON.",
)
def context_cmd(target: str, as_json: bool) -> None:
    """Implementation of `cm context`."""
    try:
        info = get_context_percent_impl(target)
    except Exception as exc:
        msg = f"context failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in info:
        if as_json:
            emit_json({"ok": False, "error": info["error"]})
            raise SystemExit(1)
        die(info["error"])
        return

    emit(info, json=as_json, fields=_CONTEXT_FIELDS)


__all__ = ["context_cmd"]
