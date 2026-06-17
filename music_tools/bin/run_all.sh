#!/bin/bash
# ============================================================
# bin/run.sh
# Konsolidierter Wrapper für alle Apple-Music-Automatisierungen.
# Läuft NUR wenn:
#   1. die 2TB SSD gemountet ist
#   2. der Mac am Stromnetz hängt
#   3. der letzte erfolgreiche Lauf >= MIN_INTERVAL_SECONDS her ist
# ============================================================

set -u

# --- Konfiguration ---
SSD_VOLUME_NAME="2TB_SSD"
SSD_MOUNT="/Volumes/$SSD_VOLUME_NAME"
MUSIC_LIBRARY_PATH="$SSD_MOUNT/Music Library [2025-06-20].musiclibrary"
MIN_INTERVAL_SECONDS=43200   # 12 h

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$REPO_DIR/scripts"
LOG_DIR="$(cd "$REPO_DIR/.." && pwd)/logs"
STATE_DIR="$REPO_DIR/state"
LOG_FILE="$LOG_DIR/run.log"
STAMP_FILE="$STATE_DIR/.last_sync"

mkdir -p "$LOG_DIR" "$STATE_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"; }

# --- Guards: SSD gemountet, Mediathek-Datei vorhanden, am Strom ---
# Skip-Fälle werden NICHT geloggt: StartOnMount feuert für jedes Volume
# (USB-Sticks, DMGs, …); sonst würde run.log mit Skips zugemüllt.
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

# Für die Kind-Skripte (sie machen denselben Preflight nochmal selbst)
export MUSIC_TOOLS_SSD_MOUNT="$SSD_MOUNT"
export MUSIC_TOOLS_LIBRARY_PATH="$MUSIC_LIBRARY_PATH"

AFFECTIVE_PLAYLISTS_DIR="$(cd "$REPO_DIR/../affective_playlists" && pwd)"
AFFECTIVE_PLAYLISTS_CMD=(/usr/bin/env python3 "$AFFECTIVE_PLAYLISTS_DIR/main.py" curate --scope fav_songs)

if [ -f "$STAMP_FILE" ]; then
    LAST=$(cat "$STAMP_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    DIFF=$((NOW - LAST))
    if [ "$DIFF" -lt "$MIN_INTERVAL_SECONDS" ]; then
        log "skip: letzter Lauf vor ${DIFF}s (min ${MIN_INTERVAL_SECONDS}s)."
        exit 0
    fi
fi

# --- Run all scripts ---
log "=== Start ==="
OVERALL_RC=0

if [ -d "$AFFECTIVE_PLAYLISTS_DIR" ]; then
    log "→ affective_playlists curate --scope fav_songs"
    if ! (cd "$AFFECTIVE_PLAYLISTS_DIR" && "${AFFECTIVE_PLAYLISTS_CMD[@]}") >> "$LOG_DIR/curate_fav_songs.log" 2>> "$LOG_DIR/curate_fav_songs.err.log"; then
        log "  curation dry-run failed; keeping existing scheduler cadence"
    fi
else
    log "missing: $AFFECTIVE_PLAYLISTS_DIR"
fi

run_script() {
    local script="$1"
    local name
    name="$(basename "$script")"
    local out="$LOG_DIR/${name}.log"
    local err="$LOG_DIR/${name}.err.log"

    log "→ $name"
    case "$script" in
        *.js)                 /usr/bin/osascript -l JavaScript "$script" >> "$out" 2>> "$err" ;;
        *.scpt|*.applescript) /usr/bin/osascript "$script" >> "$out" 2>> "$err" ;;
        *)                    log "  unbekannter Script-Typ: $script"; return 1 ;;
    esac
    local rc=$?
    log "  rc=$rc"
    return $rc
}

for s in "$SCRIPTS_DIR/sort_favourites_by_genre.js" "$SCRIPTS_DIR/route_albums_to_playlists.applescript" "$SCRIPTS_DIR/find_playlist_duplicates.js"; do
    [ -f "$s" ] || { log "missing: $s"; OVERALL_RC=1; continue; }
    run_script "$s" || OVERALL_RC=$?
done

if [ "$OVERALL_RC" -eq 0 ]; then
    date +%s > "$STAMP_FILE"
    log "=== Done OK ==="
else
    log "=== Done with errors (rc=$OVERALL_RC) ==="
fi

exit "$OVERALL_RC"
