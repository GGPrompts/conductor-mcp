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
# Predictable /tmp paths — tighten perms to prevent symlink / pre-populate
# attacks against cache-warning.json and cache-alert-*.marker writes.
chmod 700 "$STATE_DIR" "$DEBUG_DIR" "$SUBAGENT_DIR" 2>/dev/null || true

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

# Export SESSION_ID for audio-announcer.sh (ensures consistent voice outside tmux)
export CLAUDE_SESSION_ID="$SESSION_ID"

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
RUN_CACHE_HEALTH=0

# ═══════════════════════════════════════════════════════════════
# AUDIO ENABLED CHECK (cm-y7t)
# ═══════════════════════════════════════════════════════════════
# Canonical config is the single source of truth. If voice.enabled is
# present in ~/.config/conductor/config.json, honor it. Otherwise fall
# back to CLAUDE_AUDIO env var (backwards compat).
audio_is_enabled() {
    local cfg="$HOME/.config/conductor/config.json"
    if [[ -f "$cfg" ]] && command -v jq >/dev/null 2>&1; then
        # jq's // operator treats `false` as a missing value, so use an
        # explicit `has()` check to detect the key's presence separately.
        local present
        present=$(jq -r 'if (.voice // {}) | has("enabled") then "1" else "0" end' "$cfg" 2>/dev/null || echo "0")
        if [[ "$present" == "1" ]]; then
            local v
            v=$(jq -r '.voice.enabled' "$cfg" 2>/dev/null || echo "false")
            [[ "$v" == "true" ]] && return 0 || return 1
        fi
    fi
    # Fallback: CLAUDE_AUDIO=1 enables chimes
    [[ "${CLAUDE_AUDIO:-0}" == "1" ]]
}

if [[ "$HOOK_TYPE" == "pre-tool" ]] || [[ "$HOOK_TYPE" == "post-tool" ]]; then
    echo "$STDIN_DATA" > "$DEBUG_DIR/${HOOK_TYPE}-$(date +%s%N)-$$.json" 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════
# CACHE-HEALTH MONITOR (cm-8k0s)
# ═══════════════════════════════════════════════════════════════
# Passive observer: CC's prompt-cache hash can be invalidated every request
# by changing attestation data, causing 10-20x token burn with no user
# visibility. We read CC's own JSONL session logs and look for the
# signature — cache_read=0 sustained with cache_creation still growing —
# then surface a warning via state file, status line, and gated audio.
#
# Scope: only runs on post-tool (once per turn). Silent on missing inputs.
CACHE_WARNING_FILE="$STATE_DIR/cache-warning.json"

check_cache_health() {
    # Short-circuit: need jq, and post-tool only.
    command -v jq >/dev/null 2>&1 || return 0

    # CC names project dirs by replacing '/' with '-' in the abs path.
    local projects_root="$HOME/.claude/projects"
    [[ -d "$projects_root" ]] || return 0
    local dashified="${PWD//\//-}"
    local proj_dir="$projects_root/$dashified"
    [[ -d "$proj_dir" ]] || return 0

    # Most recently modified *.jsonl in the project dir (active session).
    local jsonl
    jsonl=$(ls -t "$proj_dir"/*.jsonl 2>/dev/null | head -1)
    [[ -n "$jsonl" && -f "$jsonl" ]] || return 0

    # Extract assistant entries' cache usage as TSV (read<TAB>creation).
    # Guard against malformed lines with `?` post-filter.
    local usage_tsv
    usage_tsv=$(jq -r '
        select(.type == "assistant")
        | .message.usage
        | [ (.cache_read_input_tokens // 0),
            (.cache_creation_input_tokens // 0) ]
        | @tsv
    ' "$jsonl" 2>/dev/null || true)
    [[ -n "$usage_tsv" ]] || return 0

    local total_assistants
    total_assistants=$(printf '%s\n' "$usage_tsv" | wc -l)

    # False-positive guard: need at least 8 total assistant entries.
    [[ "$total_assistants" -ge 8 ]] || return 0

    # Last 5 entries. The `total_assistants -ge 8` guard above guarantees
    # tail -n 5 returns exactly 5 lines, so no extra count check needed.
    local last5
    last5=$(printf '%s\n' "$usage_tsv" | tail -n 5)

    # Pull the single last entry (for recovery detection regardless of size).
    local last_read last_creation
    last_read=$(printf '%s\n' "$last5" | tail -n 1 | cut -f1)
    last_creation=$(printf '%s\n' "$last5" | tail -n 1 | cut -f2)

    # Recovery: most recent assistant entry has cache_read>0 → delete warning.
    if [[ "${last_read:-0}" -gt 0 ]]; then
        [[ -f "$CACHE_WARNING_FILE" ]] && rm -f "$CACHE_WARNING_FILE" 2>/dev/null || true
        return 0
    fi

    # Detection: ALL five cache_read == 0 AND cache_creation > 0 on >= 3.
    local all_reads_zero=1
    local creation_growth_count=0
    local line read_tok creation_tok
    while IFS=$'\t' read -r read_tok creation_tok; do
        [[ -n "$read_tok" ]] || continue
        if [[ "$read_tok" -ne 0 ]]; then
            all_reads_zero=0
        fi
        if [[ "$creation_tok" -gt 0 ]]; then
            creation_growth_count=$((creation_growth_count + 1))
        fi
    done <<< "$last5"

    if [[ "$all_reads_zero" -eq 1 && "$creation_growth_count" -ge 3 ]]; then
        # Derive a session-id for the marker: prefer the jsonl basename.
        local cc_session_id
        cc_session_id=$(basename "$jsonl" .jsonl)
        local detected_at
        detected_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        # Write/refresh the warning file. JSON minimal.
        jq -n \
            --arg sid "$cc_session_id" \
            --arg ts "$detected_at" \
            --argjson read 0 \
            --argjson creation "$last_creation" \
            '{session_id:$sid, detected_at:$ts, recent_cache_read:$read, recent_cache_creation:$creation}' \
            > "$CACHE_WARNING_FILE" 2>/dev/null || true

        # Audio alert (gated + rate-limited per session, 10 min).
        if audio_is_enabled; then
            local marker="$STATE_DIR/cache-alert-${cc_session_id}.marker"
            local should_fire=1
            if [[ -f "$marker" ]]; then
                local marker_age now_sec mtime
                now_sec=$(date +%s)
                mtime=$(stat -c %Y "$marker" 2>/dev/null || echo 0)
                marker_age=$((now_sec - mtime))
                [[ $marker_age -lt 600 ]] && should_fire=0
            fi
            if [[ "$should_fire" -eq 1 ]]; then
                touch "$marker" 2>/dev/null || true
                "$SCRIPT_DIR/audio-announcer.sh" cache-broken &
            fi
        fi
    fi
}

case "$HOOK_TYPE" in
    session-start)
        STATUS="idle"
        CURRENT_TOOL=""
        DETAILS='{"event":"session_started"}'
        # Cache audio_is_enabled once per invocation — config can't change
        # mid-hook, and each call spawns 2 jq processes.
        AUDIO_ENABLED=0; audio_is_enabled && AUDIO_ENABLED=1
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
        if [[ "$AUDIO_ENABLED" -eq 1 ]]; then
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
        # Cache audio_is_enabled once per invocation — config can't change
        # mid-hook, and each call spawns 2 jq processes.
        AUDIO_ENABLED=0; audio_is_enabled && AUDIO_ENABLED=1
        if [[ "$AUDIO_ENABLED" -eq 1 ]]; then
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
        # cm-8k0s: cache-health observer runs once per post-tool. Silent on
        # any missing inputs; cannot break the hook (1s timeout budget).
        # Deferred until AFTER the state file write — jq on a large JSONL
        # can be slow enough that the hook framework kills us before the
        # state file is updated for this turn.
        RUN_CACHE_HEALTH=1
        ;;
    stop)
        STATUS="awaiting_input"
        CURRENT_TOOL=""
        DETAILS='{"event":"claude_stopped","waiting_for_user":true}'
        # Cache audio_is_enabled once per invocation — config can't change
        # mid-hook, and each call spawns 2 jq processes.
        AUDIO_ENABLED=0; audio_is_enabled && AUDIO_ENABLED=1
        if [[ "$AUDIO_ENABLED" -eq 1 ]]; then
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

# Try to get context data from the context file written by the statusline script
# The statusline writes claude_session_id to our state file, which links to the context file
CONTEXT_PERCENT="null"
CONTEXT_WINDOW_SIZE="null"
TOTAL_INPUT_TOKENS="null"
TOTAL_OUTPUT_TOKENS="null"
CLAUDE_SESSION_ID=""

# Check if we have a previous state file with claude_session_id
if [[ -f "$STATE_FILE" ]]; then
    CLAUDE_SESSION_ID=$(jq -r '.claude_session_id // ""' "$STATE_FILE" 2>/dev/null || echo "")
fi

# If we have claude_session_id, try to read context data
if [[ -n "$CLAUDE_SESSION_ID" ]]; then
    CONTEXT_FILE="$STATE_DIR/${CLAUDE_SESSION_ID}-context.json"
    if [[ -f "$CONTEXT_FILE" ]]; then
        # Check if context file is fresh (within 60 seconds)
        CONTEXT_AGE=$(($(date +%s) - $(stat -c %Y "$CONTEXT_FILE" 2>/dev/null || echo 0)))
        if [[ $CONTEXT_AGE -lt 60 ]]; then
            CONTEXT_PERCENT=$(jq -r '.context_pct // "null"' "$CONTEXT_FILE" 2>/dev/null || echo "null")
            CONTEXT_WINDOW_SIZE=$(jq -r '.context_window.context_window_size // "null"' "$CONTEXT_FILE" 2>/dev/null || echo "null")
            TOTAL_INPUT_TOKENS=$(jq -r '.context_window.total_input_tokens // "null"' "$CONTEXT_FILE" 2>/dev/null || echo "null")
            TOTAL_OUTPUT_TOKENS=$(jq -r '.context_window.total_output_tokens // "null"' "$CONTEXT_FILE" 2>/dev/null || echo "null")
        fi
    fi
fi

# Build state JSON with context data when available
STATE_JSON=$(cat <<EOF
{
  "session_id": "$SESSION_ID",
  "claude_session_id": $(if [[ -n "$CLAUDE_SESSION_ID" ]]; then echo "\"$CLAUDE_SESSION_ID\""; else echo "null"; fi),
  "status": "$STATUS",
  "current_tool": "$CURRENT_TOOL",
  "subagent_count": $SUBAGENT_COUNT,
  "context_percent": $CONTEXT_PERCENT,
  "context_window": {
    "size": $CONTEXT_WINDOW_SIZE,
    "input_tokens": $TOTAL_INPUT_TOKENS,
    "output_tokens": $TOTAL_OUTPUT_TOKENS
  },
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

# cm-8k0s: run cache-health observer AFTER the state file is written. jq on a
# large JSONL can be slow enough that the hook framework's 1s timeout kills
# us; deferring ensures the state file is at least up-to-date for this turn.
# Kept inline (not backgrounded) to avoid cache-warning.json write races
# across concurrent hook invocations.
if [[ "$RUN_CACHE_HEALTH" -eq 1 ]]; then
    check_cache_health || true
fi

exit 0
