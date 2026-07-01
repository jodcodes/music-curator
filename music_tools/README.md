# 🎵 Music Tools

Legacy script home for the bundled maintenance commands that now ship through `affective_playlists tools`.

The scripts stay standalone JXA files, but the product surface is unified in `affective_playlists`.

## Was läuft

| Script | Zweck | Wo |
|---|---|---|
| `scripts/sort_favourites_by_genre.js` | Holt alle Tracks aus der Playlist „Favourite Songs" und sortiert sie in `♥ <Kategorie>` Playlisten (gleiche Fav-Songs-Genres wie affective_playlists – 1:1-Port von `curation_models.normalize_fav_genre_label`). | im Wrapper |
| `../affective_playlists/main.py curate --scope fav_songs` | Preview/Dry-Run für die neue Struktur `Fav Songs / <Genre> / Fav <Genre> <Temper>`. Läuft zusätzlich zum alten Sorter, bis die Apple-Music-Library angeschlossen und der Dry-Run akzeptiert ist. | im Wrapper |
| `scripts/route_albums_to_playlists.scpt` | Geht eine fest verdrahtete Mapping-Tabelle (Album-Name → Playlist-Name) durch und fügt seit dem letzten Lauf neu in die Library aufgenommene Tracks dieser Alben in die jeweilige Ziel-Playlist ein. | im Wrapper |
| `scripts/find_playlist_duplicates.js` | Geht alle User-Playlists durch und entfernt Duplikate. Tie-Break: eigene Tracks gewinnen gegen Apple-Music-Streaming-Tracks; bei gleicher Herkunft gewinnt das frühere `dateAdded`. Smart-Playlists und „Favourite Songs" werden übersprungen. `--dry-run` für reines Logging. | im Wrapper |
| `scripts/cleanup_old_genre_playlists.js` | **Manuell.** Löscht veraltete `♥ <Kategorie>` Playlisten, deren Name nicht mehr zur aktuellen Taxonomie von `sort_favourites_by_genre.js` passt. Betrachtet nur `♥ …` Playlisten; Smart-Playlisten/Ordner/System bleiben unangetastet. **Default Dry-Run**, echtes Löschen nur mit `--apply`. | manuell |
| `scripts/enrich_missing_genres.js` | **Manuell.** Befüllt fehlende Genre-Tags via iTunes Search API. Nur wenn Genre leer ist; bestehende Tags werden nie überschrieben. Resumable. | manuell |

`run_all.sh` führt die Wrapper-Einträge aus der Tabelle aus. Der neue Curation-Eintrag läuft vorerst nur als Preview/Dry-Run; `enrich_missing_genres.js` startest du bei Bedarf von Hand.

## Wann läuft der Wrapper

Der launchd-Agent triggert `bin/run_all.sh`. Der Wrapper läuft **nur**, wenn alle vier Bedingungen erfüllt sind:

1. **2TB SSD gemountet** (`/Volumes/2TB_SSD`)
2. **Mediathek-Datei auf der SSD vorhanden** (`/Volumes/2TB_SSD/Music Library [2025-06-20].musiclibrary`)
3. **Mac am Stromnetz** (`pmset -g ps` enthält `AC Power`)
4. **Letzter erfolgreicher Lauf ≥ 12 h her** (Stempel: `state/.last_sync`)

Zusätzlich machen die Apple-Music-Skripte denselben Preflight (SSD + Mediathek-Datei + Strom) nochmal selbst und brechen sauber ab, falls eines fehlt. So sind auch Direkt-/Manuell-Starts abgesichert (z. B. ohne Wrapper).

Trigger des Agents:
- jedes Volume-Mount (`StartOnMount`)
- alle 30 min (`StartInterval 1800`)
- beim Laden des Agents (`RunAtLoad`)

## Verzeichnisstruktur

```
music-curator/
├── logs/                                            # ALLE Logs liegen hier (eine Ebene über music_tools/)
│   ├── run.log
│   ├── sort_favourites_by_genre.log
│   ├── route_albums_to_playlists.log
│   ├── find_playlist_duplicates.log
│   ├── enrich_missing_genres.log
│   ├── launchd.stdout.log
│   └── launchd.stderr.log
└── music_tools/
    ├── bin/run_all.sh                               # Wrapper mit allen Guards
    ├── scripts/
    │   ├── sort_favourites_by_genre.js
    │   ├── route_albums_to_playlists.scpt
    │   ├── find_playlist_duplicates.js
    │   └── enrich_missing_genres.js                 # manuell, iTunes Search API
    ├── launchagents/
    │   └── com.joeldebeljak.music-tools.plist
    └── state/
        ├── .last_sync                               # Unix-Timestamp letzter Wrapper-Lauf
        ├── route_albums_lastRun.txt                 # Cutoff für Album-Router
        └── enrich_genres_state.json                 # bereits versuchte Track-IDs (resumable)
```

## Setup

```bash
chmod +x bin/run_all.sh
cp launchagents/com.joeldebeljak.music-tools.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.joeldebeljak.music-tools.plist
```

Nach plist-Änderungen:
```bash
launchctl unload ~/Library/LaunchAgents/com.joeldebeljak.music-tools.plist
launchctl load   ~/Library/LaunchAgents/com.joeldebeljak.music-tools.plist
```

## Manuell testen

```bash
bin/run_all.sh
tail -f ../logs/run.log
```

Um den 12-h-Schutz zu umgehen:
```bash
rm state/.last_sync
bin/run_all.sh
```

## Genre-Enrichment manuell starten

```bash
# Trockenlauf (schreibt nichts zurück, nur Log)
/usr/bin/osascript -l JavaScript scripts/enrich_missing_genres.js --dry-run

# Echter Lauf (~3.5s pro Track wegen Rate-Limit)
/usr/bin/osascript -l JavaScript scripts/enrich_missing_genres.js

# Live mitlesen
tail -f ../logs/enrich_missing_genres.log
```

State liegt in `state/enrich_genres_state.json`. Schon versuchte Track-IDs werden nicht erneut angefragt — du kannst den Lauf jederzeit abbrechen und später fortsetzen.

Reset (alle Tracks erneut probieren):
```bash
rm state/enrich_genres_state.json
```

## Hinweis: „Wann wurde ein Track gefavt?"

Apple Music exponiert in seinem AppleScript-Dictionary **kein** „date favorited / date loved" — nur `loved` (boolean) und `date added` (Library-Hinzufügedatum, **nicht** Fav-Datum). Bestätigt von [Doug Adams](https://dougscripts.com/itunes/itinfo/info02.php) und der [Apple-Music-Community](https://www.reddit.com/r/AppleMusic/comments/1ehkem0/can_i_see_date_added_in_favorites_songs/). Ohne offizielles Property gibt's nur Snapshot-Diff-Workarounds.

## Deinstallieren

```bash
launchctl unload ~/Library/LaunchAgents/com.joeldebeljak.music-tools.plist
rm ~/Library/LaunchAgents/com.joeldebeljak.music-tools.plist
```

## Migration

Ersetzt die alten Repos:
- `~/own_repos/music_fav_sorter/` (gelöscht)
- `~/own_repos/add_song_from_album_to_playlist/` (gelöscht)

Deren launchd-Agents (`com.joeldebeljak.music-fav-sorter`, `com.joeldebeljak.music-automation`) wurden deaktiviert.
