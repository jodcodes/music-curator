#!/bin/bash
# ============================================================
# sync_wrapper_helpers.sh
#
# Shared helpers for apple2spfy's drive-triggered sync wrapper.
# Sourced by scripts/auto_sync_on_drive.sh.template — the single source
# of truth. setup_drive_sync.sh generates the deployed wrapper FROM that
# template via sed substitution, so behavior here is identical whether
# tested directly or exercised through the generated wrapper.
# ============================================================

# Validates a python interpreter path is usable (exists, executable, runs).
# No output; returns 0/1. Caller logs context-specific messages.
validate_python_interpreter() {
    local py="$1"
    [ -n "$py" ] || return 1
    [ -x "$py" ] || return 1
    "$py" -c 'import sys' >/dev/null 2>&1
}

# Parses a raw STALE_SYNC_DAYS value; prints a valid positive integer,
# falling back to $2 (default) if $1 is empty/non-numeric/zero.
parse_stale_sync_days() {
    local raw
    raw="$(echo "$1" | tr -d '[:space:]')"
    local default="$2"
    if [[ "$raw" =~ ^[0-9]+$ ]] && [ "$raw" -gt 0 ]; then
        echo "$raw"
    else
        echo "$default"
    fi
}

# Parses a raw last-run unix timestamp; prints it if it's a valid
# nonnegative integer, else prints 0 (treated as "no valid last run").
parse_last_run_timestamp() {
    local raw
    raw="$(echo "$1" | tr -d '[:space:]')"
    if [[ "$raw" =~ ^[0-9]+$ ]]; then
        echo "$raw"
    else
        echo "0"
    fi
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    cmd="$1"
    shift
    case "$cmd" in
        validate_python_interpreter) validate_python_interpreter "$@"; exit $? ;;
        parse_stale_sync_days) parse_stale_sync_days "$@" ;;
        parse_last_run_timestamp) parse_last_run_timestamp "$@" ;;
        *) echo "usage: $0 {validate_python_interpreter|parse_stale_sync_days|parse_last_run_timestamp} args..." >&2; exit 2 ;;
    esac
fi
