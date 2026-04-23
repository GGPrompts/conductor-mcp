"""conductor.cli — the cm CLI (skeleton).

This is the empty click Group scaffolded in cm-aax.1. Verbs will be added in
cm-aax.5/.6/.7 as we migrate MCP tools over. Every subcommand added here
must:
- Expose --json for structured output (terse TSV is the default)
- Print no header row for the default TSV output (one record per line)
- Call into conductor.core, never duplicate logic from conductor.server
"""

from __future__ import annotations

import click


@click.group(
    help=(
        "cm — conductor CLI. One-shot verbs for tmux orchestration "
        "(spawn, pane ops, watch, hooks). The MCP server (conductor-mcp) "
        "and this CLI share all logic via conductor.core."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(package_name="conductor-mcp", prog_name="cm")
def cli() -> None:
    """Root command group. Subcommands are registered in cm-aax.3 onwards."""


# Entry point hook used by pyproject.toml console_scripts.
main = cli


__all__ = ["cli", "main"]
