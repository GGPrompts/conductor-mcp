"""cm watch — real-time pane monitoring (`start`, `stop`, `read`).

Migrated as part of cm-aax.7. The sub-group wraps tmux's `pipe-pane`
plumbing: `cm watch start` begins streaming a pane to a log file,
`cm watch stop` tears the pipe down, `cm watch read` tails the log.

All three subcommands call into `conductor.core`
(`watch_pane_impl`, `stop_watch_impl`, `read_watch_impl`) — the same
helpers the MCP tools `watch_pane` / `stop_watch` / `read_watch` use.

## Output shapes

- `start` / `stop`: fire-and-forget. Silent on default success,
  `{"ok": true}` on --json. Errors exit 1 with a message on stderr.
- `read`: emits the tailed log text as-is on stdout (default), or
  `{"pane_id": ..., "lines": N, "content": "..."}` on --json. This keeps
  the default mode pipe-friendly (`cm watch read %0 | grep ERROR`) while
  still exposing structured output for scripted callers.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import read_watch_impl, stop_watch_impl, watch_pane_impl


_WATCH_ERROR_PREFIX = "Failed to stop watch:"
_READ_ERROR_PREFIXES = (
    "No watch file found for ",
    "Error reading watch file:",
)


@cli.group(
    "watch",
    short_help="Stream a pane's output to a file.",
    help=(
        "Stream tmux pane output to a file for real-time monitoring. "
        "Sub-commands: start (begin piping), stop (tear down the pipe), "
        "read (tail the log)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def watch_group() -> None:
    """Parent group for all `cm watch ...` verbs."""


@watch_group.command(
    "start",
    short_help="Begin streaming a pane to a log file.",
    help=(
        "Start streaming PANE_ID's output via tmux pipe-pane. Default "
        "output file is /tmp/conductor-watch/pane-<id>.log; override "
        "with --output-file."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane_id")
@click.option(
    "--output-file",
    default=None,
    help="Custom log path (default: /tmp/conductor-watch/pane-<id>.log).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def watch_start_cmd(pane_id: str, output_file: str | None, as_json: bool) -> None:
    """Implementation of `cm watch start`."""
    try:
        result = watch_pane_impl(pane_id, output_file=output_file)
    except Exception as exc:
        msg = f"watch start failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"watch start failed: {result['error']}")
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@watch_group.command(
    "stop",
    short_help="Stop streaming a pane.",
    help="Stop streaming PANE_ID's output (closes the tmux pipe-pane).",
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
def watch_stop_cmd(pane_id: str, as_json: bool) -> None:
    """Implementation of `cm watch stop`."""
    try:
        result = stop_watch_impl(pane_id)
    except Exception as exc:
        msg = f"watch stop failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_WATCH_ERROR_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@watch_group.command(
    "read",
    short_help="Tail a pane's watch log.",
    help=(
        "Read the last --lines lines from PANE_ID's watch log. Default "
        "tail is 50 lines; --output-file overrides the auto-detected path."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane_id")
@click.option(
    "--lines",
    type=int,
    default=50,
    show_default=True,
    help="Number of lines from end to read.",
)
@click.option(
    "--output-file",
    default=None,
    help="Custom log path (default: /tmp/conductor-watch/pane-<id>.log).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"pane_id\", \"lines\", \"content\"} as single-line JSON.",
)
def watch_read_cmd(
    pane_id: str,
    lines: int,
    output_file: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm watch read`."""
    try:
        content = read_watch_impl(pane_id, lines=lines, output_file=output_file)
    except Exception as exc:
        msg = f"watch read failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    # Surface impl-level error strings as real errors (non-zero exit, stderr).
    if any(content.startswith(p) for p in _READ_ERROR_PREFIXES):
        if as_json:
            emit_json({"ok": False, "error": content})
            raise SystemExit(1)
        die(content)
        return

    if as_json:
        emit_json({"pane_id": pane_id, "lines": lines, "content": content})
        return

    # Default: emit the tailed content verbatim so `| grep` / `| tail` just work.
    import sys
    sys.stdout.write(content)
    if content and not content.endswith("\n"):
        sys.stdout.write("\n")


__all__ = [
    "watch_group",
    "watch_start_cmd",
    "watch_stop_cmd",
    "watch_read_cmd",
]
