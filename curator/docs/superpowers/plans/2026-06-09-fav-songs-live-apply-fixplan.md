# Fixplan: Fav Songs Live Apply und Betrieb

Datum: 2026-06-09

## Aktueller Stand

- `main` ist gepusht bis `8744b68 fix: route celery tasks to configured queues`.
- Live-Smoke-Test gegen Music.app war erfolgreich: 1 Track kopiert, Duplicate erkannt, Cleanup ohne Leftovers.
- Echter 1-Track-Apply lief erfolgreich als Job `curation-apply-1781022220-a2158cd0`.
- Der Apply war begrenzt auf `max_tracks=1` und hat 4 Schritte angewendet: Root-Folder, Genre-Folder, Temper-Playlist, 1 Track-Copy.
- Tests nach dem Routing-Fix: `520 passed`.
- Redis-Testcontainer und Celery-Worker wurden danach wieder gestoppt.

## Noch zu tun

- [ ] Apple Music visuell pruefen.
  - Erwartung: Der Test-Apply hat unter `Fav Songs` einen Genre-Ordner und darin eine Temper-Playlist angelegt.
  - Erwarteter Zielpfad aus dem Testlauf: `Fav Songs / Alternative / Fav Alternative Frolic`.
  - Akzeptanz: Struktur, Playlist-Name und kopierter Track sehen in Music.app so aus wie gewuenscht.

- [ ] Cleanup/Revert fuer echten 1-Track-Apply bauen.
  - Ziel: Der Test-Apply soll auch nachtraeglich aus der echten Apple-Music-Struktur entfernt werden koennen.
  - Umfang: Track aus Test-Playlist entfernen, optional leere Test-Playlist/Genre-Folder loeschen, keine fremden User-Playlists anfassen.
  - Akzeptanz: Ein Cleanup-Command oder UI-Button kann den 1-Track-Test rueckgaengig machen und meldet Leftovers.

- [ ] Full-Apply-Flow bewusst freischalten.
  - Voraussetzung: Apple-Music-Sichtpruefung und 1-Track-Cleanup sind erledigt.
  - UI-Gates: frischer Snapshot, erfolgreicher Smoke-Test, erfolgreicher 1-Track-Apply, zweite explizite Bestaetigung fuer Full Apply.
  - Akzeptanz: Full Apply kann nicht versehentlich ausgeloest werden und zeigt Jobstatus bis `completed`, `failed`, `cancelled` oder `timeout`.

- [ ] Dauerhaften Worker-Betrieb definieren.
  - Ziel: Redis und Celery sollen nicht nur als manueller Testcontainer laufen.
  - Option A: Docker Compose fuer Redis + Worker.
  - Option B: lokale Launch-/Brew-Services plus dokumentierte Worker-Kommandos.
  - Akzeptanz: UI-Apply-Jobs bleiben nicht in `queued`, wenn die App normal gestartet ist.

- [ ] MP3-Anreicherung in der UI produktiv machen.
  - Stand: Jahr/Tags und Cover-Art-Schreibpfade existieren im Code; Cover-Art wird vorsichtig nur mit MusicBrainz-ID versucht.
  - Luecke: Der Web-Enrichment-Task ist noch weitgehend simuliert und sollte auf den echten `MetadataFiller`-Pfad gehen.
  - Akzeptanz: UI kann Playlist/Folder-Enrichment als echten Job starten, Fortschritt anzeigen und Ergebnisfelder wie Jahr, Genre, BPM und Cover-Art sauber berichten.

- [ ] Queue-Hygiene fuer Entwicklungsumgebung klaeren.
  - Hintergrund: Beim Live-Test lagen alte Enrichment-Jobs in Redis, die beim Worker-Start abgearbeitet wurden und wegen fehlender DB-Jobs fehlschlugen.
  - Ziel: Dev-Start soll optional alte Testqueues leeren oder verwaiste Jobs sauber ignorieren.
  - Akzeptanz: Worker-Start erzeugt keine alten Fehlermeldungen durch verwaiste lokale Redis-Nachrichten.

## Naechster empfohlener Schritt

Zuerst Apple Music visuell pruefen und entscheiden, ob der angelegte 1-Track-Test bleiben darf. Danach den Cleanup/Revert fuer den Test-Apply bauen, bevor ein Full-Apply-Button freigeschaltet wird.
