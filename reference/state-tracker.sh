#!/bin/bash
# Claude Code State Tracker (Unified for Tmuxplexer + Terminal-Tabs)
# Writes Claude's current state to files that both projects can read

set -euo pipefail

# Get script directory for relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
STATE_DIR="/tmp/claude-code-state"
DEBUG_DIR="$STATE_DIR/debug"
SUBAGENT_DIR="$STATE_DIR/subagents"
mkdir -p "$STATE_DIR" "$DEBUG_DIR" "$SUBAGENT_DIR"

# Get tmux pane ID if running in tmux
TMUX_PANE="${TMUX_PANE:-none}"

# Read stdin if available (contains hook data from Claude)
# Always try to read stdin with timeout to avoid hanging
STDIN_DATA=$(timeout 0.1 cat 2>/dev/null || echo "")

# Get session identifier - UNIFIED STRATEGY for both projects
# Priority: 1. CLAUDE_SESSION_ID env var, 2. TMUX_PANE (for tmuxplexer), 3. Working directory hash (for terminal-tabs)
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
elif [[ "$TMUX_PANE" != "none" && -n "$TMUX_PANE" ]]; then
    SESSION_ID=$(echo "$TMUX_PANE" | sed 's/[^a-zA-Z0-9_-]/_/g')
elif [[ -n "$PWD" ]]; then
    SESSION_ID=$(echo "$PWD" | md5sum | cut -d' ' -f1 | head -c 12)
else
    SESSION_ID="$$"
fi

STATE_FILE="$STATE_DIR/${SESSION_ID}.json"
SUBAGENT_COUNT_FILE="$SUBAGENT_DIR/${SESSION_ID}.count"

get_subagent_count() {
    cat "$SUBAGENT_COUNT_FILE" 2>/dev/null || echo "0"
}

increment_subagent_count() {
    (
        flock -x 200
        local count=$(cat "$SUBAGENT_COUNT_FILE" 2>/dev/null || echo "0")
        echo $((count + 1)) > "$SUBAGENT_COUNT_FILE"
    ) 200>"$SUBAGENT_COUNT_FILE.lock"
}

decrement_subagent_count() {
    (
        flock -x 200
        local count=$(cat "$SUBAGENT_COUNT_FILE" 2>/dev/null || echo "0")
        local new_count=$((count - 1))
        [[ $new_count -lt 0 ]] && new_count=0
        echo "$new_count" > "$SUBAGENT_COUNT_FILE"
    ) 200>"$SUBAGENT_COUNT_FILE.lock"
}

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
HOOK_TYPE="${1:-unknown}"

if [[ "$HOOK_TYPE" == "pre-tool" ]] || [[ "$HOOK_TYPE" == "post-tool" ]]; then
    echo "$STDIN_DATA" > "$DEBUG_DIR/${HOOK_TYPE}-$(date +%s%N)-$$.json" 2>/dev/null || true
fi

case "$HOOK_TYPE" in
    session-start)
        STATUS="idle"
        CURRENT_TOOL=""
        DETAILS='{"event":"session_started"}'
        echo "0" > "$SUBAGENT_COUNT_FILE"
        (
            active_panes=$(tmux list-panes -a -F '#{pane_id}' 2>/dev/null | sed 's/[^a-zA-Z0-9_-]/_/g' || echo "")
            for file in "$STATE_DIR"/*.json; do
                [[ -f "$file" ]] || continue
                filename=$(basename "$file" .json)
                # Skip context files - handled separately below
                if [[ "$filename" == *-context ]]; then continue; fi
                if [[ "$active_panes" == *"$filename"* ]]; then continue; fi
                if [[ "$filename" =~ ^_[0-9]+$ ]]; then rm -f "$file"; continue; fi
                if [[ "$filename" =~ ^[a-f0-9]{12}$ ]]; then
                    file_age=$(($(date +%s) - $(stat -c %Y "$file" 2>/dev/null || echo 0)))
                    if [[ $file_age -gt 3600 ]]; then rm -f "$file"; fi
                fi
            done
            # Clean up context files older than 1 hour or orphaned (no parent state file)
            for file in "$STATE_DIR"/*-context.json; do
                [[ -f "$file" ]] || continue
                file_age=$(($(date +%s) - $(stat -c %Y "$file" 2>/dev/null || echo 0)))
                parent_file="${file/-context.json/.json}"
                if [[ ! -f "$parent_file" ]] || [[ $file_age -gt 3600 ]]; then
                    rm -f "$file"
                fi
            done
            find "$DEBUG_DIR" -name "*.json" -mmin +60 -delete 2>/dev/null || true
        ) &
        if [[ "${CLAUDE_AUDIO:-0}" == "1" ]]; then
            SESSION_NAME="${CLAUDE_SESSION_NAME:-Claude}"
            "$SCRIPT_DIR/audio-announcer.sh" session-start "$SESSION_NAME" &
        fi
        ;;
    user-prompt)
        STATUS="processing"
        CURRENT_TOOL=""
        PROMPT=$(echo "$STDIN_DATA" | jq -r '.prompt // "unknown"' 2>/dev/null || echo "unknown")
        DETAILS=$(jq -n --arg prompt "$PROMPT" '{event:"user_prompt_submitted",last_prompt:$prompt}')
        ;;
    pre-tool)
        STATUS="tool_use"
        CURRENT_TOOL=$(echo "$STDIN_DATA" | jq -r '.tool_name // .tool // .name // "unknown"' 2>/dev/null || echo "unknown")
        TOOL_ARGS_STR=$(echo "$STDIN_DATA" | jq -c '.tool_input // .input // .parameters // {}' 2>/dev/null || echo '{}')
        DETAILS=$(jq -n --arg tool "$CURRENT_TOOL" --arg args "$TOOL_ARGS_STR" '{event:"tool_starting",tool:$tool,args:($args|fromjson)}' 2>/dev/null || echo '{"event":"tool_starting"}')
        if [[ "$CURRENT_TOOL" == "Task" ]]; then increment_subagent_count; fi
        if [[ "${CLAUDE_AUDIO:-0}" == "1" ]]; then
            TOOL_DETAIL=""
            case "$CURRENT_TOOL" in
                Read|Write|Edit) TOOL_DETAIL=$(echo "$STDIN_DATA" | jq -r '.tool_input.file_path // .input.file_path // ""' 2>/dev/null | xargs basename 2>/dev/null || echo "") ;;
                Bash) TOOL_DETAIL=$(echo "$STDIN_DATA" | jq -r '.tool_input.command // .input.command // ""' 2>/dev/null | head -c 30 || echo "") ;;
                Glob|Grep) TOOL_DETAIL=$(echo "$STDIN_DATA" | jq -r '.tool_input.pattern // .input.pattern // ""' 2>/dev/null || echo "") ;;
                Task) TOOL_DETAIL=$(echo "$STDIN_DATA" | jq -r '.tool_input.description // .input.description // ""' 2>/dev/null || echo "") ;;
                WebFetch|WebSearch) TOOL_DETAIL=$(echo "$STDIN_DATA" | jq -r '.tool_input.url // .tool_input.query // .input.url // .input.query // ""' 2>/dev/null || echo "") ;;
            esac
            "$SCRIPT_DIR/audio-announcer.sh" pre-tool "$CURRENT_TOOL" "$TOOL_DETAIL" &
        fi
        ;;
    post-tool)
        STATUS="processing"
        CURRENT_TOOL=$(echo "$STDIN_DATA" | jq -r '.tool_name // .tool // .name // "unknown"' 2>/dev/null || echo "unknown")
        TOOL_ARGS_STR=$(echo "$STDIN_DATA" | jq -c '.tool_input // .input // .parameters // {}' 2>/dev/null || echo '{}')
        DETAILS=$(jq -n --arg tool "$CURRENT_TOOL" --arg args "$TOOL_ARGS_STR" '{event:"tool_completed",tool:$tool,args:($args|fromjson)}' 2>/dev/null || echo '{"event":"tool_completed"}')
        ;;
    stop)
        STATUS="awaiting_input"
        CURRENT_TOOL=""
        DETAILS='{"event":"claude_stopped","waiting_for_user":true}'
        if [[ "${CLAUDE_AUDIO:-0}" == "1" ]]; then
            SESSION_NAME="${CLAUDE_SESSION_NAME:-Claude}"
            "$SCRIPT_DIR/audio-announcer.sh" stop "$SESSION_NAME" &
        fi
        ;;
    subagent-stop)
        decrement_subagent_count
        SUBAGENT_COUNT=$(get_subagent_count)
        CURRENT_TOOL=""
        # FIX: When all subagents done, set to awaiting_input (not processing)
        # This prevents stale "processing" state when session ends after subagent work
        if [[ "$SUBAGENT_COUNT" -eq 0 ]]; then
            STATUS="awaiting_input"
            DETAILS='{"event":"subagent_stopped","remaining_subagents":0,"all_complete":true}'
        else
            STATUS="processing"
            DETAILS=$(jq -n --arg count "$SUBAGENT_COUNT" '{event:"subagent_stopped",remaining_subagents:($count|tonumber)}')
        fi
        ;;
    notification)
        NOTIF_TYPE=$(echo "$STDIN_DATA" | jq -r '.notification_type // "unknown"' 2>/dev/null || echo "unknown")
        case "$NOTIF_TYPE" in
            idle_prompt|awaiting-input)
                STATUS="awaiting_input"
                CURRENT_TOOL=""
                DETAILS='{"event":"awaiting_input_bell"}'
                ;;
            permission_prompt)
                if [[ -f "$STATE_FILE" ]]; then
                    STATUS=$(jq -r '.status // "idle"' "$STATE_FILE")
                    CURRENT_TOOL=$(jq -r '.current_tool // ""' "$STATE_FILE")
                else
                    STATUS="idle"
                    CURRENT_TOOL=""
                fi
                DETAILS='{"event":"permission_prompt"}'
                ;;
            *)
                if [[ -f "$STATE_FILE" ]]; then
                    STATUS=$(jq -r '.status // "idle"' "$STATE_FILE")
                    CURRENT_TOOL=$(jq -r '.current_tool // ""' "$STATE_FILE")
                else
                    STATUS="idle"
                    CURRENT_TOOL=""
                fi
                DETAILS=$(jq -n --arg type "$NOTIF_TYPE" '{event:"notification",type:$type}')
                ;;
        esac
        ;;
    *)
        if [[ -f "$STATE_FILE" ]]; then
            STATUS=$(jq -r '.status // "idle"' "$STATE_FILE")
            CURRENT_TOOL=$(jq -r '.current_tool // ""' "$STATE_FILE")
        else
            STATUS="idle"
            CURRENT_TOOL=""
        fi
        DETAILS=$(jq -n --arg hook "$HOOK_TYPE" '{event:"unknown_hook",hook:$hook}')
        ;;
esac

SUBAGENT_COUNT=$(get_subagent_count)

STATE_JSON=$(cat <<EOF
{
  "session_id": "$SESSION_ID",
  "status": "$STATUS",
  "current_tool": "$CURRENT_TOOL",
  "subagent_count": $SUBAGENT_COUNT,
  "working_dir": "$PWD",
  "last_updated": "$TIMESTAMP",
  "tmux_pane": "$TMUX_PANE",
  "pid": $$,
  "hook_type": "$HOOK_TYPE",
  "details": $DETAILS
}
EOF
)

echo "$STATE_JSON" > "$STATE_FILE"

if [[ "$SESSION_ID" =~ ^[a-f0-9]{12}$ ]] && [[ "$TMUX_PANE" != "none" && -n "$TMUX_PANE" ]]; then
    PANE_ID=$(echo "$TMUX_PANE" | sed 's/[^a-zA-Z0-9_-]/_/g')
    PANE_STATE_FILE="$STATE_DIR/${PANE_ID}.json"
    echo "$STATE_JSON" > "$PANE_STATE_FILE"
fi

exit 0
