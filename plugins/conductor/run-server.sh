#!/usr/bin/env bash
# Conductor MCP server launcher
# Tries multiple strategies to find and run the server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve python interpreter:
#   1. $CONDUCTOR_PYTHON override
#   2. project venv at ../../.venv (when running from repo checkout)
#   3. python3 on PATH
#   4. python on PATH
if [ -n "${CONDUCTOR_PYTHON:-}" ] && [ -x "$CONDUCTOR_PYTHON" ]; then
    PYTHON="$CONDUCTOR_PYTHON"
elif [ -x "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/../../.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: no python interpreter found on PATH." >&2
    exit 1
fi

# Strategy 1: server.py bundled alongside this script (marketplace install copies symlink)
if [ -f "$SCRIPT_DIR/server.py" ]; then
    exec "$PYTHON" "$SCRIPT_DIR/server.py"
fi

# Strategy 2: If conductor-mcp is pip-installed, use the module
if "$PYTHON" -c "import conductor_mcp" 2>/dev/null; then
    exec "$PYTHON" -m conductor_mcp.server
fi

# Strategy 3: Try uvx (if published to PyPI)
if command -v uvx &>/dev/null; then
    exec uvx conductor-mcp
fi

echo "ERROR: conductor-mcp server not found." >&2
echo "Install with: pip install -e /path/to/conductor-mcp" >&2
echo "Or clone: git clone https://github.com/GGPrompts/conductor-mcp" >&2
exit 1
