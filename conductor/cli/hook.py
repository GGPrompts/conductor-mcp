"""cm hook — tmux hook management (`set`, `clear`, `list`).

Migrated as part of cm-aax.7. Wraps tmux's `set-hook` / `show-hooks`
plumbing through `conductor.core.set_pane_hook_impl`,
`clear_hook_impl`, and `list_hooks_impl` — the same helpers the MCP
tools (`set_pane_hook`, `clear_hook`, `list_hooks`) call.

## Scope (<pane> positional)

tmux hooks attach at server-global, session, or window level — NOT
per-pane — but the established MCP verb is `set_pane_hook` and the
task spec uses `<pane>` as the positional. To keep surface parity
without breaking behaviour, the CLI accepts the positional as
`<pane>` and forwards it as the `session` argument of the impls
(tmux treats a pane id like `%0` as a valid `-t` target because it
resolves to the containing session). Pass `--global` to install the
hook with `-g` instead.

## Output shapes

- `set` / `clear`: fire-and-forget. Silent on default success,
  `{"ok": true}` on --json. Impl-level errors ("Failed to set hook: ..."
  / "Invalid event. ...") exit 1 with the message on stderr.
- `list`: terse TSV `pane_id<TAB>event<TAB>cmd` default (no header,
  one record per line). On --json, emits `[{"pane_id", "event",
  "command"}, ...]` as single-line JSON. The `pane_id` field echoes
  whatever target the user asked about ("" when --global).
"""

from __future__ import annotations

import sys

import click

from conductor.cli import cli
from conductor.cli._output import _escape_tsv_value, die, emit_json
from conductor.core import clear_hook_impl, list_hooks_impl, set_pane_hook_impl


_HOOK_SET_ERROR_PREFIXES = ("Failed to set hook:", "Invalid event.")
_HOOK_CLEAR_ERROR_PREFIX = "Failed to clear hook:"


@cli.group(
    "hook",
    help=(
        "Manage tmux event hooks. Sub-commands: set (register a hook), "
        "clear (remove a hook), list (show active hooks)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def hook_group() -> None:
    """Parent group for all `cm hook ...` verbs."""


@hook_group.command(
    "set",
    help=(
        "Register EVENT to run COMMAND for PANE. PANE is a tmux target "
        "(pane id like %0, or a session name) — pass --global to scope "
        "the hook server-wide instead. Valid events: pane-died, "
        "pane-exited, pane-focus-in, pane-focus-out, pane-mode-changed, "
        "pane-set-clipboard."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane")
@click.argument("event")
@click.argument("command")
@click.option(
    "--global",
    "as_global",
    is_flag=True,
    default=False,
    help="Install the hook globally (ignore PANE, use tmux -g).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def hook_set_cmd(
    pane: str,
    event: str,
    command: str,
    as_global: bool,
    as_json: bool,
) -> None:
    """Implementation of `cm hook set`."""
    session_arg = None if as_global else pane

    try:
        result = set_pane_hook_impl(event, command, session=session_arg)
    except Exception as exc:
        msg = f"hook set failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if any(result.startswith(p) for p in _HOOK_SET_ERROR_PREFIXES):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@hook_group.command(
    "clear",
    help=(
        "Remove EVENT hook from PANE. PANE is a tmux target (pane id "
        "or session name) — pass --global to clear a server-wide hook."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane")
@click.argument("event")
@click.option(
    "--global",
    "as_global",
    is_flag=True,
    default=False,
    help="Clear the global hook (ignore PANE, use tmux -gu).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def hook_clear_cmd(pane: str, event: str, as_global: bool, as_json: bool) -> None:
    """Implementation of `cm hook clear`."""
    session_arg = None if as_global else pane

    try:
        result = clear_hook_impl(event, session=session_arg)
    except Exception as exc:
        msg = f"hook clear failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if result.startswith(_HOOK_CLEAR_ERROR_PREFIX):
        if as_json:
            emit_json({"ok": False, "error": result})
            raise SystemExit(1)
        die(result)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@hook_group.command(
    "list",
    help=(
        "List active hooks. Default is global scope (tmux -g); pass "
        "--session to scope to a specific session. Terse TSV output: "
        "pane_id<TAB>event<TAB>cmd per line, no header."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--session",
    default=None,
    help="Scope the listing to a session (default: global).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit [{pane_id, event, command}, ...] as single-line JSON.",
)
def hook_list_cmd(session: str | None, as_json: bool) -> None:
    """Implementation of `cm hook list`."""
    try:
        hooks = list_hooks_impl(session=session)
    except Exception as exc:
        msg = f"hook list failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    # `list_hooks_impl` returns `[{"event", "command"}]`. For the surface the
    # task spec asks for, echo the scoping target as pane_id (empty on global).
    scope = session or ""
    records = [
        {"pane_id": scope, "event": h.get("event", ""), "command": h.get("command", "")}
        for h in hooks
    ]

    if as_json:
        emit_json(records)
        return

    # Terse TSV: pane_id<TAB>event<TAB>cmd, no header, one record per line.
    out = sys.stdout
    for r in records:
        row = [
            _escape_tsv_value(r["pane_id"]),
            _escape_tsv_value(r["event"]),
            _escape_tsv_value(r["command"]),
        ]
        out.write("\t".join(row))
        out.write("\n")


__all__ = [
    "hook_group",
    "hook_set_cmd",
    "hook_clear_cmd",
    "hook_list_cmd",
]
