"""cm capture — capture recent output from a worker's tmux pane.

Migrated as part of cm-aax.9 (polling migration). Wraps
`conductor.core.capture_worker_output_impl()` — the same helper the MCP
`capture_worker_output` tool calls.

## Output shape

Default mode writes the captured pane text to stdout verbatim so the
output is trivially composable (`cm capture BD-abc | tail -20`). A
capture failure is surfaced as a non-zero exit with a "Failed to capture:
..." message on stderr. `--json` wraps the result as
`{"session": ..., "lines": N, "content": "..."}` for scripted callers.
"""

from __future__ import annotations

import sys

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import capture_worker_output_impl


_CAPTURE_ERROR_PREFIX = "Failed to capture:"


@cli.command(
    "capture",
    short_help="Tail recent lines from a session's pane.",
    help=(
        "Capture the last --lines lines from SESSION's tmux pane. "
        "Default tail is 50 lines. Emits the raw pane text on stdout; "
        "use --json for {session, lines, content}."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("session")
@click.option(
    "--lines",
    type=int,
    default=50,
    show_default=True,
    help="Number of lines from end to capture.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {session, lines, content} as single-line JSON.",
)
def capture_cmd(session: str, lines: int, as_json: bool) -> None:
    """Implementation of `cm capture`."""
    try:
        content = capture_worker_output_impl(session, lines=lines)
    except Exception as exc:
        msg = f"capture failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    # The impl returns an inline error string on tmux failure — surface it.
    if content.startswith(_CAPTURE_ERROR_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": content.strip()})
            raise SystemExit(1)
        die(content.strip())
        return

    if as_json:
        emit_json({"session": session, "lines": lines, "content": content})
        return

    # Default: emit captured text verbatim for `| grep` / `| tail` use.
    sys.stdout.write(content)
    if content and not content.endswith("\n"):
        sys.stdout.write("\n")


__all__ = ["capture_cmd"]
