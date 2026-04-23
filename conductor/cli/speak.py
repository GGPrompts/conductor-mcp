"""cm speak — TTS announcement verb (canonical CLI/MCP parity example).

This is the reference implementation every other migrated verb in
cm-aax.5/.6/.7 should copy from. The pattern:

1. Register on the `cm` click group imported from `conductor.cli`.
2. Accept the same logical arguments as the MCP tool (positional text +
   voice/rate/pitch/volume options). Every verb exposes `--json`.
3. Call `conductor.core.<verb>_impl(...)` — never import from
   `conductor.server`. The MCP wrapper calls the same `_impl`, guaranteeing
   the two surfaces stay in lockstep.
4. On success: default (no `--json`) is silent (empty TSV stream); `--json`
   prints `{"ok": true}` (or a richer shape when the verb has return data).
5. On failure: write a message to stderr via `_output.die()` and exit 1.
   `--json` emits `{"ok": false, "error": "..."}` on stdout AND still exits
   non-zero so shell scripts can `if ! cm speak ...`.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import speak_impl


# Known prefixes that `speak_impl` returns on failure. speak_impl doesn't
# raise for expected errors — it returns a short string — so we pattern-match
# the prefix to decide whether the run was a success. Keep this in sync with
# the return paths in conductor.core.speak_impl.
_ERROR_PREFIXES = (
    "TTS generation failed",
    "edge-tts not found",
    "Audio busy",
    "Audio cached at",  # fallback: cached but no player installed
)

# Non-error but non-speaking returns (audio gate off). Treat as success: the
# gate is doing its job, this is not a failure mode.
_GATED_PREFIXES = (
    "audio disabled",
)


@cli.command(
    "speak",
    help=(
        "Speak TEXT aloud using edge-tts. Silent on success by default; "
        "pass --json for a structured {\"ok\": true} result."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("text")
@click.option(
    "--voice",
    default=None,
    help="Edge TTS voice (defaults to voice.default in config).",
)
@click.option(
    "--rate",
    default=None,
    help="Speech rate (e.g. '+20%', '-10%'). Defaults to voice.rate in config.",
)
@click.option(
    "--pitch",
    default=None,
    help="Pitch (e.g. '+0Hz'). Defaults to voice.pitch in config.",
)
@click.option(
    "--volume",
    default=None,
    help="Volume (e.g. '+0%'). Defaults to voice.volume in config.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def speak_cmd(
    text: str,
    voice: str | None,
    rate: str | None,
    pitch: str | None,
    volume: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm speak`."""
    result = speak_impl(
        text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        blocking=False,
        priority=True,
    )

    # Classify the return. speak_impl returns short status strings rather
    # than raising, so we match against known prefixes.
    is_error = any(result.startswith(p) for p in _ERROR_PREFIXES)
    is_gated = any(result.startswith(p) for p in _GATED_PREFIXES)

    if is_error:
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return  # unreachable; die() exits

    # Success (including gated "audio disabled" — the gate is working).
    if as_json:
        if is_gated:
            emit_json({"ok": True, "gated": True, "reason": result})
        else:
            emit_json({"ok": True})
        return

    # Default TSV mode: silent on success (no records → no output).
    # The return string ("Speaking: ...") is only useful for interactive
    # debugging; users who want it can add --json.
    return


__all__ = ["speak_cmd"]
