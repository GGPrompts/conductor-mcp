#!/bin/bash
# Tmux Status Bar Integration for Claude Code
# Shows real-time Claude activity in tmux status bar
#
# Installation:
#   1. Make executable: chmod +x ~/.claude/hooks/tmux-status-claude.sh
#   2. Add to ~/.tmux.conf:
#      set -g status-right '#(~/.claude/hooks/tmux-status-claude.sh) | %H:%M %d-%b'
#   3. Reload tmux: tmux source-file ~/.tmux.conf

STATE_DIR="/tmp/claude-code-state"

# Get current tmux session and pane
# When running from status bar, TMUX_PANE isn't set, so get it from tmux directly
CURRENT_SESSION=$(tmux display-message -p '#S' 2>/dev/null || echo "")
CURRENT_PANE=$(tmux display-message -p '#{pane_id}' 2>/dev/null || echo "")

# If we can't get session info, we're not in tmux
if [[ -z "$CURRENT_SESSION" ]]; then
    echo ""
    exit 0
fi

# Check if ANY pane in current session is running Claude
# (Previous version only checked :0.0 which missed Claude in other panes/windows)
CLAUDE_FOUND=false
while IFS= read -r line; do
    if [[ "$line" =~ claude ]]; then
        CLAUDE_FOUND=true
        break
    fi
done < <(tmux list-panes -s -t "$CURRENT_SESSION" -F '#{pane_current_command}' 2>/dev/null)

if [[ "$CLAUDE_FOUND" != "true" ]]; then
    # No Claude running in this session
    echo ""
    exit 0
fi

# Try to find state file for THIS session's Claude
# Sanitize pane ID for filename
PANE_ID=$(echo "$CURRENT_PANE" | sed 's/[^a-zA-Z0-9_-]/_/g')
STATE_FILE="$STATE_DIR/${PANE_ID}.json"

# Fallback: try to find by working directory of current pane
if [[ ! -f "$STATE_FILE" ]]; then
    # Use current pane's path, not hardcoded :0.0
    PANE_PWD=$(tmux display-message -p '#{pane_current_path}' 2>/dev/null || echo "$PWD")
    PWD_HASH=$(echo "$PANE_PWD" | md5sum | cut -d' ' -f1 | head -c 12)
    STATE_FILE="$STATE_DIR/${PWD_HASH}.json"
fi

# If still no match, don't show anything (don't fall back to random Claude session!)
if [[ ! -f "$STATE_FILE" ]]; then
    echo ""
    exit 0
fi

# Read state
STATUS=$(jq -r '.status // ""' "$STATE_FILE" 2>/dev/null)
CURRENT_TOOL=$(jq -r '.current_tool // ""' "$STATE_FILE" 2>/dev/null)
LAST_UPDATED=$(jq -r '.last_updated // ""' "$STATE_FILE" 2>/dev/null)

# Check if state is fresh (within 60 seconds)
if [[ -n "$LAST_UPDATED" ]]; then
    UPDATED_SEC=$(date -d "$LAST_UPDATED" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$LAST_UPDATED" +%s 2>/dev/null)
    CURRENT_SEC=$(date +%s)
    AGE=$((CURRENT_SEC - UPDATED_SEC))

    if [[ $AGE -gt 60 ]]; then
        # Stale state, don't show
        echo ""
        exit 0
    fi
fi

# Format output based on status
# NOTE: Using ASCII instead of emojis to avoid tmux width calculation issues
# (emojis are 2-cells wide but tmux treats them as 1-cell, causing status bar cutoff)
case "$STATUS" in
    idle)
        echo "[OK] Ready"
        ;;
    processing)
        echo "[..] Processing"
        ;;
    tool_use)
        if [[ -n "$CURRENT_TOOL" ]]; then
            # Try to extract detail from args
            DETAIL=""

            # Get file_path for Read/Edit/Write
            FILE_PATH=$(jq -r '.details.args.file_path // ""' "$STATE_FILE" 2>/dev/null)
            if [[ -n "$FILE_PATH" ]] && [[ "$FILE_PATH" != "null" ]]; then
                # Show just filename
                DETAIL=$(basename "$FILE_PATH")
            fi

            # Get command for Bash
            if [[ -z "$DETAIL" ]]; then
                COMMAND=$(jq -r '.details.args.command // ""' "$STATE_FILE" 2>/dev/null)
                if [[ -n "$COMMAND" ]] && [[ "$COMMAND" != "null" ]]; then
                    # Truncate long commands
                    if [[ ${#COMMAND} -gt 30 ]]; then
                        DETAIL="${COMMAND:0:30}..."
                    else
                        DETAIL="$COMMAND"
                    fi
                fi
            fi

            # Get pattern for Grep/Glob
            if [[ -z "$DETAIL" ]]; then
                PATTERN=$(jq -r '.details.args.pattern // ""' "$STATE_FILE" 2>/dev/null)
                if [[ -n "$PATTERN" ]] && [[ "$PATTERN" != "null" ]]; then
                    if [[ ${#PATTERN} -gt 25 ]]; then
                        DETAIL="${PATTERN:0:25}..."
                    else
                        DETAIL="$PATTERN"
                    fi
                fi
            fi

            # Output (truncate to prevent status bar overflow)
            if [[ -n "$DETAIL" ]]; then
                # Truncate detail to 15 chars max
                DETAIL="${DETAIL:0:15}"
                echo "[>] ${CURRENT_TOOL:0:10}: ${DETAIL}"
            else
                echo "[>] ${CURRENT_TOOL:0:15}"
            fi
        else
            echo "[>] Tool"
        fi
        ;;
    working)
        if [[ -n "$CURRENT_TOOL" ]]; then
            echo "[*] ${CURRENT_TOOL}"
        else
            echo "[*] Working"
        fi
        ;;
    awaiting_input)
        echo "[||] Awaiting"
        ;;
    *)
        # Unknown status, don't show
        echo ""
        ;;
esac
