"""cm spawn — worker-spawn verbs.

Migrated as part of cm-aax.6. `cm spawn in-pane` mirrors the MCP
`spawn_worker_in_pane` tool; both call
`conductor.core.spawn_worker_in_pane_impl()`.

The sub-group anticipates future sibling verbs (e.g. `cm spawn wave`,
`cm spawn smart`) without churning the CLI surface.
"""

from __future__ import annotations

import click

from conductor.cli import cli
from conductor.cli._output import die, emit_json, emit_tsv


_IN_PANE_FIELDS = ["pane_id", "issue_id", "worktree", "branch", "context_injected"]


@cli.group(
    "spawn",
    help=(
        "Spawn workers into tmux. Sub-commands: in-pane (launch a worker "
        "in an existing pane by id)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def spawn_group() -> None:
    """Parent group for all `cm spawn ...` verbs."""


@spawn_group.command(
    "in-pane",
    short_help="Launch a worker in an existing pane.",
    help=(
        "Launch a worker in existing PANE_ID for beads ISSUE_ID. Creates "
        "a git worktree under <cwd>/.worktrees/ISSUE_ID if missing and "
        "optionally injects beads context after the agent boots."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("pane_id")
@click.argument("issue_id")
@click.option(
    "--cwd",
    "project_dir",
    required=True,
    help="Path to the main project directory (becomes .worktrees root).",
)
@click.option(
    "--profile",
    "profile_cmd",
    default="claude",
    show_default=True,
    help="Agent command to launch (e.g. claude, codex, gemini -i).",
)
@click.option(
    "--inject-context/--no-inject-context",
    "inject_context",
    default=True,
    help="Inject beads issue context after the agent boots.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit single-line JSON instead of TSV.",
)
def spawn_in_pane_cmd(
    pane_id: str,
    issue_id: str,
    project_dir: str,
    profile_cmd: str,
    inject_context: bool,
    as_json: bool,
) -> None:
    """Implementation of `cm spawn in-pane`."""
    from conductor.core import spawn_worker_in_pane_impl

    try:
        result = spawn_worker_in_pane_impl(
            pane_id=pane_id,
            issue_id=issue_id,
            project_dir=project_dir,
            profile_cmd=profile_cmd,
            inject_context=inject_context,
        )
    except Exception as exc:
        msg = f"spawn in-pane failed: {exc}"
        if as_json:
            emit_json({"ok": False, "error": msg})
            raise SystemExit(1)
        die(msg)
        return

    if "error" in result:
        if as_json:
            emit_json({"ok": False, "error": result["error"]})
            raise SystemExit(1)
        die(f"spawn in-pane failed: {result['error']}")
        return

    if as_json:
        emit_json(result)
        return

    emit_tsv([result], _IN_PANE_FIELDS)


__all__ = ["spawn_group", "spawn_in_pane_cmd"]
