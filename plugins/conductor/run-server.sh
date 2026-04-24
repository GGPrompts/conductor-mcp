#!/usr/bin/env bash
# Conductor MCP server launcher
# Tries multiple strategies to find and run the server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Strategy 1: global conductor-mcp command on PATH
# (installed via `uv tool install --editable .` — tracks repo edits live)
if command -v conductor-mcp &>/dev/null; then
    exec conductor-mcp
fi

# Strategy 2: python -m conductor.server from the repo checkout at ../..
# Used when the plugin is loaded from a working tree without global install.
REPO_ROOT="$SCRIPT_DIR/../.."
if [ -f "$REPO_ROOT/conductor/server.py" ]; then
    # Resolve python interpreter:
    #   1. $CONDUCTOR_PYTHON override
    #   2. project venv at ../../.venv
    #   3. python3 on PATH
    #   4. python on PATH
    if [ -n "${CONDUCTOR_PYTHON:-}" ] && [ -x "$CONDUCTOR_PYTHON" ]; then
        PYTHON="$CONDUCTOR_PYTHON"
    elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
        PYTHON="$REPO_ROOT/.venv/bin/python"
    elif command -v python3 &>/dev/null; then
        PYTHON=python3
    elif command -v python &>/dev/null; then
        PYTHON=python
    else
        echo "ERROR: no python interpreter found on PATH." >&2
        exit 1
    fi
    cd "$REPO_ROOT"
    exec "$PYTHON" -m conductor.server
fi

# Strategy 3: uvx fallback (if ever published to PyPI)
if command -v uvx &>/dev/null; then
    exec uvx conductor-mcp
fi

echo "ERROR: conductor-mcp server not found." >&2
echo "Install globally with: uv tool install --editable /path/to/conductor-mcp" >&2
echo "Or clone: git clone https://github.com/GGPrompts/conductor-mcp" >&2
exit 1
