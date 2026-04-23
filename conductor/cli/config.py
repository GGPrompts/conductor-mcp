"""cm config — read-only config access (`get`).

Migrated as part of cm-aax.7. `cm config get` mirrors the MCP
`get_config` tool and calls `conductor.core.get_config_impl()`.

User-facing config mutation (voice picker, profile CRUD, timing) lives
in the conductor-tui Settings panel (cm-3gw) by design — the CLI stays
read-only so scripts never inadvertently drift config on the user.

## Output shape

The full config is a nested dict (voice.*, delays.*, profiles.*, ...).
Default TSV renders one dot-path key per line: `key<TAB>value`, no
header. Non-scalar leaves (lists, nested structures that remain after
flattening) are JSON-encoded so each row stays one record on one line.

With --json, emits the full config dict as single-line JSON.
"""

from __future__ import annotations

import json as _json
import sys

import click

from conductor.cli import cli
from conductor.cli._output import _escape_tsv_value, die, emit_json, flatten_config
from conductor.core import get_config_impl


@cli.group(
    "config",
    help="Inspect conductor config. Sub-commands: get (read current config).",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def config_group() -> None:
    """Parent group for all `cm config ...` verbs."""


@config_group.command(
    "get",
    help=(
        "Print the current conductor config. Default is flat TSV "
        "(one dot-path key per line, tab-separated from its value). "
        "Use --json for the raw nested dict."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full config as single-line JSON.",
)
def config_get_cmd(as_json: bool) -> None:
    """Implementation of `cm config get`."""
    try:
        cfg = get_config_impl()
    except Exception as exc:
        msg = f"config get failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json(cfg)
        return

    # Default: flat TSV. Non-scalar leaves get JSON-encoded so each row stays
    # one record (the contract in _output.py docs). Lists of profiles live
    # under keys like `profiles.claude` after flattening — we JSON-encode
    # them rather than str()-ing so consumers can round-trip cleanly.
    out = sys.stdout
    for key, value in flatten_config(cfg):
        if isinstance(value, (list, dict)):
            rendered = _json.dumps(value)
        else:
            rendered = _escape_tsv_value(value)
        out.write(f"{_escape_tsv_value(key)}\t{rendered}\n")


__all__ = ["config_group", "config_get_cmd"]
