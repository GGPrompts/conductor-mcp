#!/usr/bin/env bash
# Conductor MCP server launcher
# Tries multiple strategies to find and run the server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Strategy 1: server.py bundled alongside this script (marketplace install copies symlink)
if [ -f "$SCRIPT_DIR/server.py" ]; then
    exec python "$SCRIPT_DIR/server.py"
fi

# Strategy 2: If conductor-mcp is pip-installed, use the module
if python -c "import conductor_mcp" 2>/dev/null; then
    exec python -m conductor_mcp.server
fi

# Strategy 3: Try uvx (if published to PyPI)
if command -v uvx &>/dev/null; then
    exec uvx conductor-mcp
fi

echo "ERROR: conductor-mcp server not found." >&2
echo "Install with: pip install -e /path/to/conductor-mcp" >&2
echo "Or clone: git clone https://github.com/GGPrompts/conductor-mcp" >&2
exit 1
