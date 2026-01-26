#!/bin/bash
# Claude Code Audio Announcer
# Speaks status changes using Edge TTS with configurable voices
#
# Usage: audio-announcer.sh <event> [session_name] [detail]
# Events: stop, session-start, user-prompt, pre-tool, post-tool, error
#
# Configuration: ~/.claude/audio-config.sh
# Environment variables override config file settings

set -euo pipefail

EVENT="${1:-unknown}"
SESSION_NAME="${2:-Claude}"
DETAIL="${3:-}"  # Optional detail (filename, command, pattern, etc.)

# ═══════════════════════════════════════════════════════════════
# LOAD CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CONFIG_FILE="$HOME/.claude/audio-config.sh"
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

# Apply config with env var overrides
VOICE="${CLAUDE_VOICE:-${DEFAULT_VOICE:-en-US-AndrewMultilingualNeural}}"
RATE="${CLAUDE_RATE:-${DEFAULT_RATE:-+0%}}"
PITCH="${CLAUDE_PITCH:-${DEFAULT_PITCH:-+0Hz}}"
VOLUME="${CLAUDE_VOLUME:-${DEFAULT_VOLUME:-+0%}}"
SPEED="${CLAUDE_SPEED:-${PLAYBACK_SPEED:-1.0}}"
DEBOUNCE_MS="${TOOL_DEBOUNCE_MS:-1000}"

# Feature toggles (default to true if not set)
ANNOUNCE_TOOLS="${ANNOUNCE_TOOLS:-true}"
ANNOUNCE_SESSION_START="${ANNOUNCE_SESSION_START:-true}"
ANNOUNCE_READY="${ANNOUNCE_READY:-true}"

# Audio directories
AUDIO_DIR="/tmp/claude-audio-cache"
CLIPS_DIR="${CUSTOM_CLIPS_DIR:-}"
AUDIO_LOCK="/tmp/claude-audio.lock"
DEBUG_LOG="/tmp/audio-debug.log"
mkdir -p "$AUDIO_DIR"

# ═══════════════════════════════════════════════════════════════
# AUDIO MUTEX (prevent simultaneous announcements from subagents)
# ═══════════════════════════════════════════════════════════════
# Tool announcements use nonblock (skip if busy)
# Critical announcements (ready, session-start) wait briefly

acquire_audio_lock() {
    local wait_mode="${1:-nonblock}"  # nonblock or wait
    exec 9>"$AUDIO_LOCK"
    if [[ "$wait_mode" == "wait" ]]; then
        # Wait up to 3 seconds for lock
        flock -w 3 9 2>/dev/null || return 1
    else
        # Non-blocking: fail immediately if locked
        flock --nonblock 9 2>/dev/null || return 1
    fi
    return 0
}

release_audio_lock() {
    exec 9>&-
}

# ═══════════════════════════════════════════════════════════════
# DEBOUNCE CHECK (for tool announcements)
# ═══════════════════════════════════════════════════════════════
DEBOUNCE_FILE="/tmp/claude-audio-last-tool"

should_debounce() {
    [[ "$DEBOUNCE_MS" == "0" ]] && return 1  # Debounce disabled

    local now=$(date +%s%N | cut -c1-13)  # Current time in ms
    local last=$(cat "$DEBOUNCE_FILE" 2>/dev/null || echo "0")
    local diff=$((now - last))

    if (( diff < DEBOUNCE_MS )); then
        return 0  # Should debounce (skip this announcement)
    fi

    echo "$now" > "$DEBOUNCE_FILE"
    return 1  # Don't debounce (play this announcement)
}

# ═══════════════════════════════════════════════════════════════
# PLAY CUSTOM CLIP (if available)
# ═══════════════════════════════════════════════════════════════
# Usage: play_clip <clip_name> [sync]
# If sync is "sync", waits for playback to complete (for mutex)
play_clip() {
    local clip_name="$1"
    local sync_mode="${2:-async}"
    if [[ -n "$CLIPS_DIR" && -f "$CLIPS_DIR/${clip_name}.mp3" ]]; then
        if [[ "$sync_mode" == "sync" ]]; then
            mpv --no-video --really-quiet --speed="$SPEED" "$CLIPS_DIR/${clip_name}.mp3" &>/dev/null
        else
            mpv --no-video --really-quiet --speed="$SPEED" "$CLIPS_DIR/${clip_name}.mp3" &>/dev/null &
        fi
        return 0
    fi
    return 1  # No clip found
}

# ═══════════════════════════════════════════════════════════════
# SPEAK TEXT (TTS with caching)
# ═══════════════════════════════════════════════════════════════
# Usage: speak <text> [sync]
# If sync is "sync", waits for playback to complete (for mutex)
speak() {
    local text="$1"
    local sync_mode="${2:-async}"
    # Include voice + rate in cache key
    local cache_key=$(echo "${VOICE}:${RATE}:${PITCH}:${text}" | md5sum | cut -d' ' -f1)
    local cache_file="$AUDIO_DIR/${cache_key}.mp3"

    echo "[$(date)] speak() text='$text' sync=$sync_mode cache=$cache_file" >> "$DEBUG_LOG"

    # Generate if not cached
    if [[ ! -f "$cache_file" ]]; then
        echo "[$(date)] generating audio..." >> "$DEBUG_LOG"
        edge-tts -v "$VOICE" --rate "$RATE" --pitch "$PITCH" --volume "$VOLUME" \
            -t "$text" --write-media "$cache_file" 2>>"$DEBUG_LOG" || { echo "[$(date)] edge-tts failed" >> "$DEBUG_LOG"; return 1; }
        echo "[$(date)] generated: $(ls -la "$cache_file" 2>&1)" >> "$DEBUG_LOG"
    else
        echo "[$(date)] using cached file" >> "$DEBUG_LOG"
    fi

    # Play (with optional speed adjustment)
    if [[ -f "$cache_file" ]]; then
        echo "[$(date)] playing with mpv (sync=$sync_mode)..." >> "$DEBUG_LOG"
        if [[ "$sync_mode" == "sync" ]]; then
            mpv --no-video --really-quiet --speed="$SPEED" "$cache_file" 2>>"$DEBUG_LOG"
            echo "[$(date)] mpv exited: $?" >> "$DEBUG_LOG"
        else
            mpv --no-video --really-quiet --speed="$SPEED" "$cache_file" &>/dev/null &
        fi
    else
        echo "[$(date)] cache file missing after generation!" >> "$DEBUG_LOG"
    fi
}

case "$EVENT" in
    stop)
        echo "[$(date)] stop event, ANNOUNCE_READY=$ANNOUNCE_READY" >> "$DEBUG_LOG"
        [[ "$ANNOUNCE_READY" != "true" ]] && exit 0
        echo "[$(date)] acquiring lock..." >> "$DEBUG_LOG"
        # Critical: wait for lock (up to 3s), play sync to hold lock during playback
        acquire_audio_lock "wait" || { echo "[$(date)] lock failed" >> "$DEBUG_LOG"; exit 0; }
        echo "[$(date)] lock acquired, calling speak..." >> "$DEBUG_LOG"
        play_clip "ready" "sync" || speak "$SESSION_NAME ready for input" "sync"
        echo "[$(date)] speak done" >> "$DEBUG_LOG"
        release_audio_lock
        ;;

    session-start)
        [[ "$ANNOUNCE_SESSION_START" != "true" ]] && exit 0
        # Critical: wait for lock (up to 3s), play sync to hold lock during playback
        acquire_audio_lock "wait" || exit 0
        play_clip "session-start" "sync" || speak "$SESSION_NAME session started" "sync"
        release_audio_lock
        ;;

    user-prompt)
        # Optional: could announce "Processing" but might be annoying
        # speak "$SESSION_NAME processing"
        ;;

    pre-tool)
        [[ "$ANNOUNCE_TOOLS" != "true" ]] && exit 0
        should_debounce && exit 0  # Skip if too soon after last announcement

        # Non-blocking: skip if another announcement is already playing
        # This prevents subagent tool floods from overlapping
        acquire_audio_lock "nonblock" || exit 0

        # SESSION_NAME = tool name, DETAIL = relevant info (filename, pattern, etc.)
        TOOL_NAME="$SESSION_NAME"

        # Build announcement with detail if available (sync mode to hold lock)
        if [[ -n "$DETAIL" ]]; then
            case "$TOOL_NAME" in
                Read) speak "Reading $DETAIL" "sync" ;;
                Write) speak "Writing $DETAIL" "sync" ;;
                Edit) speak "Editing $DETAIL" "sync" ;;
                Bash) speak "Running $DETAIL" "sync" ;;
                Glob) speak "Finding $DETAIL" "sync" ;;
                Grep) speak "Searching $DETAIL" "sync" ;;
                Task) speak "Agent: $DETAIL" "sync" ;;
                WebFetch) speak "Fetching $DETAIL" "sync" ;;
                WebSearch) speak "Searching $DETAIL" "sync" ;;
                *) speak "$TOOL_NAME $DETAIL" "sync" ;;
            esac
        else
            # Fallback without detail (sync mode to hold lock)
            case "$TOOL_NAME" in
                Read) speak "Reading" "sync" ;;
                Write) speak "Writing" "sync" ;;
                Edit) speak "Editing" "sync" ;;
                Bash) speak "Running command" "sync" ;;
                Glob) speak "Searching files" "sync" ;;
                Grep) speak "Searching code" "sync" ;;
                Task) speak "Spawning agent" "sync" ;;
                WebFetch) speak "Fetching web" "sync" ;;
                WebSearch) speak "Searching web" "sync" ;;
                *) speak "Using $TOOL_NAME" "sync" ;;
            esac
        fi
        release_audio_lock
        ;;

    post-tool)
        # Optional: announce tool completion
        # play_clip "done" || speak "Done"
        ;;

    build-pass)
        play_clip "build-pass" || speak "Build successful"
        ;;

    tests-pass)
        play_clip "tests-pass" || speak "Tests passing"
        ;;

    error)
        play_clip "error" || speak "$SESSION_NAME encountered an error"
        ;;

    summary)
        # For future: could trigger the brief summary here
        # gemini-media brief --since "5 min" --speak &
        ;;

    *)
        # Unknown event, don't speak
        ;;
esac

exit 0
