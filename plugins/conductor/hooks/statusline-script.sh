#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract data from JSON
model_name=$(echo "$input" | jq -r '.model.display_name // .model.id')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
output_style=$(echo "$input" | jq -r '.output_style.name // "default"')
transcript_path=$(echo "$input" | jq -r '.transcript_path // ""')
session_id=$(echo "$input" | jq -r '.session_id // ""')

# Color codes (using bright/high-intensity colors without bold to reduce flickering)
GREEN='\033[92m'
BLUE='\033[94m'
YELLOW='\033[93m'
MAGENTA='\033[95m'
CYAN='\033[96m'
RED='\033[91m'
GRAY='\033[90m'
# Simple reset
RESET='\033[0m'
BOLD='\033[1m'

# Initialize status parts array
status_parts=()

# Calculate session ID the same way as state-tracker.sh (for subagent count)
# Priority: 1. CLAUDE_SESSION_ID env var, 2. TMUX_PANE (for tmux), 3. Working directory hash, 4. PID
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
elif [[ "${TMUX_PANE:-none}" != "none" && -n "${TMUX_PANE:-}" ]]; then
    # Use tmux pane ID (sanitize for filename - same as state-tracker.sh)
    SESSION_ID=$(echo "$TMUX_PANE" | sed 's/[^a-zA-Z0-9_-]/_/g')
elif [[ -n "$current_dir" ]]; then
    SESSION_ID=$(echo "$current_dir" | md5sum | cut -d' ' -f1 | head -c 12)
else
    SESSION_ID="$$"
fi

STATE_FILE="/tmp/claude-code-state/${SESSION_ID}.json"

# Read subagent count from state-tracker file
subagent_count=0
if [ -f "$STATE_FILE" ]; then
    subagent_count=$(jq -r '.subagent_count // 0' "$STATE_FILE" 2>/dev/null)
fi

# Extract context_window data and write to separate context state file
# This allows the conductor to read token usage and context percentage
context_window=$(echo "$input" | jq -c '.context_window // null')
current_usage=$(echo "$input" | jq -c '.context_window.current_usage // null')

if [ "$context_window" != "null" ] && [ -n "$session_id" ]; then
    CONTEXT_FILE="/tmp/claude-code-state/${session_id}-context.json"

    # Calculate context percentage using cache tokens (closest to /context display)
    context_pct=""
    context_window_size=$(echo "$context_window" | jq -r '.context_window_size // 0')

    if [ "$current_usage" != "null" ]; then
        input_tokens=$(echo "$current_usage" | jq -r '.input_tokens // 0')
        cache_creation=$(echo "$current_usage" | jq -r '.cache_creation_input_tokens // 0')
        cache_read=$(echo "$current_usage" | jq -r '.cache_read_input_tokens // 0')

        # Total = input + cache tokens (approximates actual context usage)
        total_tokens=$((input_tokens + cache_creation + cache_read))

        if [ "$context_window_size" -gt 0 ]; then
            context_pct=$((total_tokens * 100 / context_window_size))
        fi
    fi

    # Write context data to file for conductor to read
    mkdir -p /tmp/claude-code-state
    echo "$input" | jq -c "{
        session_id: .session_id,
        context_window: .context_window,
        context_pct: ${context_pct:-null},
        timestamp: now | todateiso8601
    }" > "$CONTEXT_FILE" 2>/dev/null

    # Also update the state file with claude_session_id so backend can link context data
    # Note: state file already has session_id (pane-based), we add claude_session_id for context lookup
    if [ -f "$STATE_FILE" ]; then
        jq --arg sid "$session_id" '.claude_session_id = $sid' "$STATE_FILE" > "${STATE_FILE}.tmp" 2>/dev/null && mv "${STATE_FILE}.tmp" "$STATE_FILE"
    fi
fi

# 3. Current Directory (with ~ substitution)
formatted_dir=$(echo "$current_dir" | sed "s|^$HOME|~|")
status_parts+=("${BLUE}${formatted_dir}${RESET}")

# 4. Git Branch (if in git repository)
if git rev-parse --git-dir >/dev/null 2>&1; then
    # Skip git locks to avoid blocking
    git_branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    git_status=""
    
    # Check for uncommitted changes (quick check)
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        git_status="*"
    elif ! git diff-index --quiet --cached HEAD -- 2>/dev/null; then
        git_status="+"
    fi
    
    status_parts+=("${YELLOW}⎇ ${git_branch}${git_status}${RESET}")
fi

# 5. Python Virtual Environment
if [ -n "$VIRTUAL_ENV" ]; then
    venv_name=$(basename "$VIRTUAL_ENV")
    status_parts+=("${MAGENTA}🐍 ${venv_name}${RESET}")
fi

# 6. Context Window Usage (if available)
if [ -n "$context_pct" ] && [ "$context_pct" != "null" ]; then
    # Color-code based on usage: green < 50%, yellow < 75%, red >= 75%
    if [ "$context_pct" -lt 50 ]; then
        ctx_color="$GREEN"
    elif [ "$context_pct" -lt 75 ]; then
        ctx_color="$YELLOW"
    else
        ctx_color="$RED"
    fi
    status_parts+=("${ctx_color}${context_pct}% ctx${RESET}")
fi

# 7. Claude Model (with subagent robots)
if [ "$model_name" != "null" ] && [ -n "$model_name" ]; then
    # Clean up model name for display (remove "Claude" prefix, keep version numbers)
    display_model=$(echo "$model_name" | sed 's/^Claude //; s/3.5 Sonnet/3.5S/; s/3 Opus/3O/; s/3 Haiku/3H/')

    # Build robot string: 🤖 for main + extra 🤖 for each active subagent
    robots="🤖"
    for ((i=0; i<subagent_count; i++)); do
        robots+="🤖"
    done

    status_parts+=("${MAGENTA}${robots} ${display_model}${RESET}")
fi

# 8. Output Style (if not default)
if [ "$output_style" != "null" ] && [ "$output_style" != "default" ] && [ -n "$output_style" ]; then
    status_parts+=("${CYAN}📝 ${output_style}${RESET}")
fi

# 9. Exit Code of Last Command (if available from environment)
if [ -n "$CLAUDE_LAST_EXIT_CODE" ] && [ "$CLAUDE_LAST_EXIT_CODE" != "0" ]; then
    status_parts+=("${RED}✗ ${CLAUDE_LAST_EXIT_CODE}${RESET}")
fi

# 10. Docker Context (if docker is available)
if command -v docker >/dev/null 2>&1; then
    # Redirect both stdout and stderr to avoid WSL Docker integration messages
    docker_context=$(docker context show 2>/dev/null)
    if [ $? -eq 0 ] && [ "$docker_context" != "default" ] && [ -n "$docker_context" ]; then
        status_parts+=("${BLUE}🐳 ${docker_context}${RESET}")
    fi
fi

# Join all parts with separator
separator="${GRAY} │ ${RESET}"
status_line=""
for i in "${!status_parts[@]}"; do
    if [ $i -eq 0 ]; then
        status_line="${status_parts[i]}"
    else
        status_line="${status_line}${separator}${status_parts[i]}"
    fi
done

# Print the final status line
printf "%b\n" "$status_line"