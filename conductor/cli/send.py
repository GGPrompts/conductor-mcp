"""cm send — send keys to a tmux session (optionally submit with Enter).

Migrated as part of cm-aax.5. Mirrors the MCP `send_keys` tool; both call
`conductor.core.send_keys_impl()` so behaviour stays identical.

Default is to submit (type text, wait 0.8s, press Enter) — matching the
MCP tool default. Pass `--no-submit` to only type the text.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import DEFAULT_DELAY_MS, send_keys_impl


@cli.command(
    "send",
    short_help="Send text to a tmux session.",
    help=(
        "Send TEXT to SESSION via tmux send-keys. Submits with Enter by "
        "default after --delay-ms milliseconds. Use --no-submit to type "
        "without submitting (useful for partial input)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("session")
@click.argument("text")
@click.option(
    "--submit/--no-submit",
    default=True,
    help="Submit after typing by pressing Enter (default: --submit).",
)
@click.option(
    "--delay-ms",
    type=int,
    default=DEFAULT_DELAY_MS,
    show_default=True,
    help="Milliseconds to wait between text and Enter (ignored with --no-submit).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def send_cmd(
    session: str,
    text: str,
    submit: bool,
    delay_ms: int,
    as_json: bool,
) -> None:
    """Implementation of `cm send`."""
    try:
        send_keys_impl(session, text, submit=submit, delay_ms=delay_ms)
    except Exception as exc:  # subprocess.CalledProcessError, etc.
        msg = f"send failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json({"ok": True})
        return
    # Default TSV mode: silent on success.
    return


__all__ = ["send_cmd"]
