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
    epilog=(
        "Examples:\n"
        "\n"
        "\b\n"
        "  cm list workers                 # active tmux sessions (TSV)\n"
        "  cm send my-sess 'hello'         # type 'hello' + Enter\n"
        "  cm capture my-sess --lines 20   # tail pane output\n"
        "  cm grid 2x2                     # split current pane into a grid\n"
        "  cm config get --json            # dump full config\n"
        "\n"
        "Every verb supports --json for single-line structured output; "
        "default is terse TSV (no header). Run `cm <verb> --help` for details."
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
from conductor.cli import capture as _capture  # noqa: F401  (registers capture)
from conductor.cli import config as _config  # noqa: F401  (registers config group)
from conductor.cli import context as _context  # noqa: F401  (registers context)
from conductor.cli import focus as _focus  # noqa: F401  (registers focus)
from conductor.cli import grid as _grid  # noqa: F401  (registers grid)
from conductor.cli import hook as _hook  # noqa: F401  (registers hook group)
from conductor.cli import kill as _kill  # noqa: F401  (registers kill group)
from conductor.cli import layout as _layout  # noqa: F401  (registers layout group)
from conductor.cli import list as _list  # noqa: F401  (registers list group)
from conductor.cli import popup as _popup  # noqa: F401  (registers popup group)
from conductor.cli import resize as _resize  # noqa: F401  (registers resize)
from conductor.cli import send as _send  # noqa: F401  (registers send)
from conductor.cli import session as _session  # noqa: F401  (registers session group)
from conductor.cli import spawn as _spawn  # noqa: F401  (registers spawn group)
from conductor.cli import speak as _speak  # noqa: F401  (registers speak)
from conductor.cli import split as _split  # noqa: F401  (registers split)
from conductor.cli import watch as _watch  # noqa: F401  (registers watch group)
from conductor.cli import window as _window  # noqa: F401  (registers window group)
from conductor.cli import worker as _worker  # noqa: F401  (registers worker group)
from conductor.cli import zoom as _zoom  # noqa: F401  (registers zoom)


__all__ = ["cli", "main"]
