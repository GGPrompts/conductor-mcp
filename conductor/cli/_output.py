"""conductor.cli._output — shared output helpers for `cm` subcommands.

Every `cm` verb follows the CLI policy in CLAUDE.md:
- Default stdout is terse TSV: no header row, one record per line. Values are
  escaped so the stream stays parseable by `awk -F$'\\t'` / `cut -f1` — tabs
  become spaces, literal newlines inside string values become a single space.
- `--json` emits a single-line `json.dumps(obj)` + trailing newline (never
  `indent=2`; the line is pipeline-friendly). Shape matches the MCP return
  shape field-for-field (see conductor.protocol).
- Errors go to `sys.stderr`; the process exits non-zero via `sys.exit(1)`.
  stdout stays clean so `cm ... | jq` / `cm ... | cut -f1` never see error
  text mixed with data.
- Empty result sets write nothing to stdout (silent success). This is what
  scripts expect from a terse CLI — no "no results" banner to filter out.

Subcommand modules import `emit()` / `emit_tsv()` / `emit_json()` / `die()`.
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any, Iterable


def _escape_tsv_value(value: Any) -> str:
    """Render a single value for a TSV cell.

    - None -> empty string (keeps column count stable).
    - bool -> "true" / "false" (matches JSON output rendering).
    - Any other non-string -> str(value).
    - Strings have embedded tabs / CR / LF collapsed to a single space so
      one record stays one line and column boundaries stay well-defined.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if not isinstance(value, str):
        value = str(value)
    # Collapse whitespace that would break the one-record-per-line contract.
    return (
        value.replace("\t", " ")
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def emit_tsv(records: Iterable[dict], fields: list[str]) -> None:
    """Write records as tab-separated lines to stdout, no header.

    Each record contributes one line. `fields` is the ordered column list;
    missing keys render as empty cells (same as None). The caller picks the
    field order — stable across invocations is a CLI contract.
    """
    out = sys.stdout
    for record in records:
        row = [_escape_tsv_value(record.get(f)) for f in fields]
        out.write("\t".join(row))
        out.write("\n")


def emit_json(obj: Any) -> None:
    """Write obj as a single-line JSON document + newline to stdout."""
    sys.stdout.write(_json.dumps(obj))
    sys.stdout.write("\n")


def emit(
    obj: Any,
    *,
    json: bool,
    fields: list[str] | None = None,
) -> None:
    """Convenience dispatcher: emit_json() when --json, else emit_tsv().

    `obj` shape rules:
    - For TSV: `obj` must be a list[dict] (possibly empty). `fields` is
      required so column order is explicit.
    - For JSON: `obj` can be any JSON-serialisable value. Single record
      commands typically pass a dict; list commands pass a list[dict].
    """
    if json:
        emit_json(obj)
        return

    if fields is None:
        # TSV mode demands explicit columns; refuse to guess silently.
        raise ValueError("emit(): `fields` is required when json=False")

    if isinstance(obj, dict):
        records: Iterable[dict] = [obj]
    elif isinstance(obj, list):
        records = obj
    else:
        raise TypeError(
            f"emit(): TSV output needs dict or list[dict], got {type(obj).__name__}"
        )

    emit_tsv(records, fields)


def die(message: str, *, exit_code: int = 1) -> None:
    """Write an error message to stderr and exit non-zero.

    stdout is NOT touched — callers can pipe `cm ... | jq` safely and know
    errors never poison the data stream. Always use this for user-visible
    failures; raising click.ClickException also works but prints to stderr
    with a "Error: " prefix which we don't always want.
    """
    sys.stderr.write(message)
    if not message.endswith("\n"):
        sys.stderr.write("\n")
    sys.exit(exit_code)


__all__ = [
    "emit",
    "emit_tsv",
    "emit_json",
    "die",
]
