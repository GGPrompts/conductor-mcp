"""cm worker — worker-scoped introspection (`status`, `capacity`).

Migrated as part of cm-aax.9 (polling migration). Wraps pure helpers in
`conductor.core` (`get_worker_status_impl`, `get_workers_with_capacity_impl`)
— the same helpers the MCP tools `get_worker_status` /
`get_workers_with_capacity` call.

## Output shapes

- `cm worker status <session>`: reads the Claude state file for a single
  worker. Default is TSV with one `key<TAB>value` pair per line (non-scalar
  values JSON-encoded so rows stay one record). `--json` emits the raw
  dict. When no state file exists, the command exits non-zero with a
  "no state for <session>" message on stderr (the MCP tool returned None,
  which doesn't translate to a useful default stdout shape).

- `cm worker capacity`: returns per-worker context-capacity buckets.
  Default TSV emits one row per worker, sorted by bucket + context%:
  session<TAB>context_percent<TAB>claude_status<TAB>attached<TAB>bucket
  — where `bucket` is `with_capacity` or `at_capacity`. `--json` emits
  the full summary dict (workers_with_capacity, workers_at_capacity,
  totals) matching the prior MCP return shape.
"""

from __future__ import annotations

import json as _json
import sys

import click

from conductor.cli import cli
from conductor.cli._output import _escape_tsv_value, die, emit, emit_json
from conductor.core import (
    get_worker_status_impl,
    get_workers_with_capacity_impl,
)


_CAPACITY_FIELDS = [
    "session",
    "context_percent",
    "claude_status",
    "attached",
    "bucket",
]


@cli.group(
    "worker",
    help=(
        "Worker introspection. Sub-commands: status (read Claude state "
        "for a session), capacity (find workers below a context threshold)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def worker_group() -> None:
    """Parent group for all `cm worker ...` verbs."""


@worker_group.command(
    "status",
    help=(
        "Read Claude's state file for SESSION. Exits non-zero with a "
        "message on stderr when no state file exists. Default TSV emits "
        "one key<TAB>value pair per line (non-scalar values JSON-encoded). "
        "Use --json for the raw dict."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("session")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full state dict as single-line JSON.",
)
def worker_status_cmd(session: str, as_json: bool) -> None:
    """Implementation of `cm worker status`."""
    try:
        state = get_worker_status_impl(session)
    except Exception as exc:
        msg = f"worker status failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if state is None:
        msg = f"no state for {session}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json(state)
        return

    # Default: flat TSV — one key<TAB>value per line. Non-scalar values
    # JSON-encoded so rows stay one record per line (matches `cm config get`).
    out = sys.stdout
    for key, value in state.items():
        if isinstance(value, (list, dict)):
            rendered = _json.dumps(value)
        else:
            rendered = _escape_tsv_value(value)
        out.write(f"{_escape_tsv_value(key)}\t{rendered}\n")


@worker_group.command(
    "capacity",
    help=(
        "List workers and their remaining context capacity. Default TSV "
        "columns: session<TAB>context_percent<TAB>claude_status<TAB>"
        "attached<TAB>bucket (bucket is 'with_capacity' or 'at_capacity'). "
        "Use --json for the summary dict."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--threshold",
    type=int,
    default=60,
    show_default=True,
    help="Context %% below which a worker is considered to have capacity.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the full summary dict as single-line JSON.",
)
def worker_capacity_cmd(threshold: int, as_json: bool) -> None:
    """Implementation of `cm worker capacity`."""
    try:
        summary = get_workers_with_capacity_impl(threshold=threshold)
    except Exception as exc:
        msg = f"worker capacity failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json(summary)
        return

    # Default TSV: one row per worker, bucket annotated as a field.
    records: list[dict] = []
    for w in summary.get("workers_with_capacity", []):
        rec = dict(w)
        rec["bucket"] = "with_capacity"
        records.append(rec)
    for w in summary.get("workers_at_capacity", []):
        rec = dict(w)
        rec["bucket"] = "at_capacity"
        records.append(rec)

    emit(records, json=False, fields=_CAPACITY_FIELDS)


__all__ = ["worker_group", "worker_status_cmd", "worker_capacity_cmd"]
