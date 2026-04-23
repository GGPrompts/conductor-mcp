"""conductor — orchestration package for Claude Code workers.

Layout mirrors therminal's core/protocol/cli/server split:
- conductor.core      — pure tmux/config/voice helpers (no MCP or CLI awareness)
- conductor.protocol  — shared return-shape TypedDicts used by both surfaces
- conductor.server    — FastMCP server (MCP surface)
- conductor.cli       — click CLI (cm binary)

Both surfaces are thin wrappers over conductor.core.
"""

__version__ = "0.1.0"
