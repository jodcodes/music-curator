# 📝 TODO

## Verifikation (vor Abschluss der Migration)
- [x] 2TB SSD anstecken + Mac am Strom → echten Lauf abwarten (05.05.2026 11:11–11:17)
- [x] `logs/run.log` prüfen: `=== Done OK ===`
- [x] `logs/sort_favourites_by_genre.js.log` zeigt sortierte Tracks (45 Faved + 784 Monthly)
- [ ] `logs/route_albums_to_playlists.log` zeigt erfolgreiche Album-→-Playlist-Adds (heute keine Adds, weil alles schon drin war; neues Detail-Logging beim nächsten Lauf prüfen)
- [x] `state/.last_sync` wird geschrieben
- [ ] `state/route_albums_lastRun.txt` wird geschrieben — **Bug fix am 05.05.2026 deployed** (POSIX-file-Pfad), beim nächsten Lauf verifizieren
- [x] `state/faved_snapshot.json` wird aktualisiert

## Aufräumen (nach erfolgreichem Verifikationslauf)
- [x] `~/own_repos/music_fav_sorter/` löschen
- [x] `~/own_repos/add_song_from_album_to_playlist/` löschen
- [x] Alte Crontab-Einträge prüfen: `crontab -l | grep -i music` → keine vorhanden
- [x] Alte LaunchAgents prüfen: `~/Library/LaunchAgents/` → nur `com.joeldebeljak.music-tools.plist` aktiv

## Git
- [ ] `git init` + initial commit
- [ ] Remote anlegen (GitHub) und pushen

## Mögliche Verbesserungen
- [ ] Volume-Name `2TB_SSD` als Variable in `bin/run_all.sh` evtl. nach `bin/config.sh` auslagern
- [ ] `MIN_INTERVAL_SECONDS` (12 h) konfigurierbar machen
- [ ] Log-Rotation für `logs/*.log` (z. B. via `newsyslog.d` oder einfacher Größen-Check im Wrapper)
- [ ] Notification bei Fehlern (z. B. via `osascript -e 'display notification ...'`)
- [ ] Healthcheck-Script: `bin/status.sh` → zeigt letzten Lauf, nächste geplante Ausführung, SSD-/Power-Status
- [ ] Smoke-Test-Modus (`bin/run_all.sh --dry-run`) ohne tatsächliche Music-API-Calls
- [ ] `enrich_missing_genres.js` einmal komplett laufen lassen (~75 min für 1500 Tracks); danach Verteilung erneut prüfen

## Dokumentation
- [ ] README-Screenshot der Playlisten-Struktur ergänzen
- [x] Beschreibung der `route_albums_to_playlists.scpt`-Logik (welche Alben → welche Playlist) im README ergänzt (in der Tabelle)
