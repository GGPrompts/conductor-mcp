"""cm popup — display-popup helpers (`show` + `status`).

Migrated as part of cm-aax.5.

## Why a sub-group (`cm popup show` / `cm popup status`)?

The MCP surface has `show_popup` (arbitrary text) and `show_status_popup`
(pre-formatted worker summary), with more popup variants likely to follow
(e.g. capacity summary, error popups). A flat CLI would need
`cm popup` + `cm popup-status` + future ad-hoc names, which is noisy.

The sub-group composes cleanly: `cm popup <kind>`. We explicitly chose the
sub-sub form over a `--status` flag on `cm popup` because:

- `--status` would have to make the positional MESSAGE argument optional
  AND mutually exclusive with the flag, which click doesn't express
  cleanly and confuses `--help` output.
- Every future popup kind would need another flag + exclusion rule; with
  the sub-group each kind is just another `@popup_group.command(...)`.

Both subcommands call `conductor.core.show_popup_impl()` /
`show_status_popup_impl()` — the same helpers the MCP tools use.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json
from conductor.core import show_popup_impl, show_status_popup_impl


@cli.group(
    "popup",
    help=(
        "Display floating tmux popups. Sub-commands: show (arbitrary text), "
        "status (pre-formatted worker status summary)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def popup_group() -> None:
    """Parent group for all `cm popup ...` verbs."""


@popup_group.command(
    "show",
    help="Show MESSAGE in a floating tmux popup.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("message")
@click.option(
    "--title",
    default="Conductor",
    show_default=True,
    help="Popup title.",
)
@click.option(
    "--width",
    type=int,
    default=50,
    show_default=True,
    help="Popup width in columns.",
)
@click.option(
    "--height",
    type=int,
    default=10,
    show_default=True,
    help="Popup height in rows.",
)
@click.option(
    "--duration-s",
    type=int,
    default=3,
    show_default=True,
    help="How long the popup stays visible (seconds).",
)
@click.option(
    "--target",
    default=None,
    help="Target pane/session (default: current).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def popup_show_cmd(
    message: str,
    title: str,
    width: int,
    height: int,
    duration_s: int,
    target: str | None,
    as_json: bool,
) -> None:
    """Implementation of `cm popup show`."""
    try:
        show_popup_impl(
            message=message,
            title=title,
            width=width,
            height=height,
            duration_s=duration_s,
            target=target,
        )
    except Exception as exc:
        msg = f"popup show failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


@popup_group.command(
    "status",
    help="Show worker status summary in a popup.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--target",
    default=None,
    help="Target pane/session (default: current).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit {\"ok\": true} / {\"ok\": false, \"error\": ...} as single-line JSON.",
)
def popup_status_cmd(target: str | None, as_json: bool) -> None:
    """Implementation of `cm popup status`."""
    try:
        show_status_popup_impl(target=target)
    except Exception as exc:
        msg = f"popup status failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if as_json:
        emit_json({"ok": True})
        return
    return


__all__ = ["popup_group", "popup_show_cmd", "popup_status_cmd"]
