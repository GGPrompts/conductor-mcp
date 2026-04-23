"""conductor.cli — the cm CLI (scaffold + parity guarantee).

Subcommands register themselves on the `cli` click.Group by decorating with
`@cli.command(...)` or `@cli.group(...)`. The import block at the bottom of
this module is what actually triggers registration — if you add a new verb
module (e.g. `conductor/cli/pane.py`), add a matching `from conductor.cli
import pane  # noqa: F401  (registers)` line below. Every subcommand must:

- Expose `--json` for structured output (terse TSV is the default).
- Print no header row for the default TSV output (one record per line).
- Call into `conductor.core.<verb>_impl(...)`, never duplicate logic from
  `conductor.server`.

## Naming convention (IMPORTANT — binds cm-aax.5/.6/.7 migrations)

MCP tool names are flat snake_case (`speak`, `list_panes`, `list_hooks`,
`smart_spawn_wave`). The CLI may expose the same verbs as either:

1. Flat, matching the MCP name exactly: `cm speak`, `cm smart_spawn`.
2. Grouped as `<noun> <verb>`, replacing the underscore: `list_hooks` →
   `cm hook list`, `list_panes` → `cm pane list`, `set_pane_hook` →
   `cm hook set`. Use grouping when the noun already has ≥2 related verbs.

`tests/test_surface_parity.py` enforces both surfaces carry the same set of
shared verbs. When a CLI path differs from the MCP name, add a mapping to
`CLI_PATH_MAP` in that test module.
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
    """Root command group. Subcommands register via sibling-module imports."""


def main() -> None:
    """Console-script entry point referenced by pyproject.toml."""
    cli()


# ─── Subcommand registration ────────────────────────────────────
# Each import registers a verb on `cli` as a side-effect. Keep this list
# alphabetised; add a new line for every new verb module. Noqa on each
# import because the module-level decorator is the whole point.
from conductor.cli import focus as _focus  # noqa: F401  (registers focus)
from conductor.cli import kill as _kill  # noqa: F401  (registers kill group)
from conductor.cli import popup as _popup  # noqa: F401  (registers popup group)
from conductor.cli import send as _send  # noqa: F401  (registers send)
from conductor.cli import speak as _speak  # noqa: F401  (registers speak)


__all__ = ["cli", "main"]
