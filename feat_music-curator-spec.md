# Music Curator — Spec für Claude Code

## Ziel
Playlisten in der Apple Musik-App durchgehen, pro Track prüfen ob eine lokale Datei (Festplatte/iCloud) existiert, und wenn ja, den Track im lokalen Bestand mit dieser Datei verknüpfen/ersetzen (statt reinem Cloud-/Streaming-Verweis).

## Technischer Ansatz
- **Music.app AppleScript-Bridge** nutzen (wie in dieser Session für Calendar/Notes) oder `osxphotos`-artige Python-Library für Music (z.B. `music.app`-Scripting via `appscript`/`osascript`).
- Pro Playlist: `every track` durchgehen, `location` property prüfen:
  - Wenn `location` gesetzt → Track hat bereits eine lokale Datei, nichts zu tun.
  - Wenn `location` leer/missing → Track ist reiner Cloud-/Matched-Verweis ohne lokale Datei.
- Für Tracks ohne lokale Datei: in einem definierten lokalen Musik-Ordner (Pfad mit Joel klären) nach Datei mit passendem Artist+Titel suchen (Fuzzy-Match, z.B. via `rapidfuzz` in Python).
- Bei Treffer: Datei der Music-App-Bibliothek hinzufügen und den Playlist-Eintrag auf die lokale Datei umbiegen (`add` + Track ersetzen, da Music.app kein direktes "swap location" erlaubt).

## Offene Punkte (mit Joel vor Umsetzung klären)
- Genauer Pfad des lokalen Musikordners/der Festplatte, die als Quelle für Ersatzdateien dient.
- Was bei mehreren Treffern (mehrere Versionen/Remixes) passieren soll — automatisch bestes Match nehmen oder Liste zur manuellen Entscheidung ausgeben?
- **Vibe & Genre Curator**: laut Todo-Liste existiert dafür schon ein Teil-Setup ("fertig machen"), aber ohne Zugriff auf den bestehenden Code kann ich das nicht mit-specen. Beim Claude-Code-Termin am besten den bestehenden Stand zeigen, dann darauf aufbauen statt neu spec.
