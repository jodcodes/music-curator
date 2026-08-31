#!/bin/bash
# ============================================================
# bin/run_sync.sh
# Wrapper für den monatlichen Spotify → Apple Music Sync.
# Läuft NUR wenn:
#   1. die 2TB SSD gemountet ist
#   2. der Mac am Stromnetz hängt
#   3. der letzte erfolgreiche Lauf >= COOLDOWN_SECONDS her ist
# ============================================================

set -u

# --- Konfiguration ---
SSD_VOLUME_NAME="2TB_SSD"
SSD_MOUNT="/Volumes/$SSD_VOLUME_NAME"
MUSIC_LIBRARY_PATH="$SSD_MOUNT/Media (Musik Mediathek)/Music Library [2025-06-20].musiclibrary"
COOLDOWN_SECONDS=$((30 * 86400))   # 30 Tage

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
STATE_DIR="$SCRIPT_DIR/state"
LOG_FILE="$LOG_DIR/spfy2apple.log"
ERROR_FILE="$LOG_DIR/spfy2apple.err.log"
STAMP_FILE="$STATE_DIR/.last_sync"
FAILURE_FILE="$STATE_DIR/.last_failure"
FAILURE_COOLDOWN_SECONDS=3600   # 1 h Retry-Sperre nach Fehler

mkdir -p "$LOG_DIR" "$STATE_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"; }

# --- Guards: SSD gemountet, Mediathek-Datei vorhanden, am Strom ---
if [ ! -d "$SSD_MOUNT" ]; then
    exit 0
fi

if [ ! -e "$MUSIC_LIBRARY_PATH" ]; then
    log "skip: SSD gemountet, aber Mediathek-Datei fehlt ($MUSIC_LIBRARY_PATH)."
    exit 0
fi

if ! /usr/bin/pmset -g ps | grep -q "AC Power"; then
    log "skip: SSD gemountet, aber kein Strom (Akkubetrieb)."
    exit 0
fi

# --- Cooldown: letzter erfolgreicher Lauf >= 30 Tage her ---
if [ -f "$STAMP_FILE" ]; then
    LAST=$(cat "$STAMP_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    DIFF=$((NOW - LAST))
    if [ "$DIFF" -lt "$COOLDOWN_SECONDS" ]; then
        DAYS_LEFT=$(((COOLDOWN_SECONDS - DIFF) / 86400))
        log "skip: letzter Lauf vor ${DIFF}s (noch ${DAYS_LEFT}d bis zum nächsten Sync)."
        exit 0
    fi
fi

# --- Fehler-Cooldown: nicht bei jedem Mount-Event retryen ---
if [ -f "$FAILURE_FILE" ]; then
    LAST_FAILURE=$(cat "$FAILURE_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    if [ "$((NOW - LAST_FAILURE))" -lt "$FAILURE_COOLDOWN_SECONDS" ]; then
        MINS_LEFT=$(((FAILURE_COOLDOWN_SECONDS - (NOW - LAST_FAILURE)) / 60))
        log "skip: letzter Sync fehlgeschlagen, Retry in ${MINS_LEFT}m."
        exit 0
    fi
fi

# --- Sync ausführen ---
PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    log "[FAIL] Python im venv nicht gefunden: $PYTHON"
    exit 1
fi

log "=== Start ==="
cd "$SCRIPT_DIR" || { log "[FAIL] cannot cd to $SCRIPT_DIR"; exit 1; }

if "$PYTHON" sync_from_spotify.py --apply >> "$LOG_FILE" 2>> "$ERROR_FILE"; then
    date +%s > "$STAMP_FILE"
    rm -f "$FAILURE_FILE"
    log "=== Done OK ==="
    exit 0
else
    rc=$?
    date +%s > "$FAILURE_FILE"
    log "=== Done with errors (rc=$rc) ==="
    exit "$rc"
fi
