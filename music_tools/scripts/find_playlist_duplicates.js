#!/usr/bin/env osascript -l JavaScript
// ============================================================
// find_playlist_duplicates.js (JXA – JavaScript for Automation)
//
// Geht alle User-Playlists durch und findet Tracks, die mehr als
// einmal in derselben Playlist hinzugefügt wurden.
//
// Tie-Break-Regeln, welcher Track BLEIBT:
//   1. Eigene Tracks (kein Apple-Music-Streaming) gewinnen gegen
//      Apple-Music-Subscription-Tracks (cloudStatus === "subscription").
//   2. Bei gleicher Herkunft: früheres dateAdded gewinnt.
//   3. Bei gleichem dateAdded: erstes Vorkommen in der Playlist.
//
// Standard: Duplikate werden ENTFERNT. Mit --dry-run nur loggen,
// nichts anfassen.
//
// Smart-Playlists und die Hauptbibliothek werden übersprungen.
// "Favourite Songs" wird ebenfalls übersprungen (System-Playlist,
// Tracks lassen sich i. d. R. nicht per Script entfernen).
//
// Manuell starten:
//   /usr/bin/osascript -l JavaScript scripts/find_playlist_duplicates.js
//   /usr/bin/osascript -l JavaScript scripts/find_playlist_duplicates.js --dry-run
// ============================================================

ObjC.import("Foundation");

const Music = Application("Music");
Music.includeStandardAdditions = true;
const App = Application.currentApplication();
App.includeStandardAdditions = true;

const HOME = $.NSHomeDirectory().js;
const BASE_DIR = `${HOME}/own_repos/music-curator/music_tools`;
const LOG_DIR = `${HOME}/own_repos/music-curator/logs`;
const LOG_FILE = `${LOG_DIR}/find_playlist_duplicates.log`;
const ERROR_FILE = `${LOG_DIR}/find_playlist_duplicates.err.log`;

// --- Preflight: SSD gemountet, Mediathek-Datei vorhanden, am Strom ---
const SSD_MOUNT = "/Volumes/2TB_SSD";
const MUSIC_LIBRARY_PATH = `${SSD_MOUNT}/Music Library [2025-06-20].musiclibrary`;

// Gibt einen Skip-Grund (String) zurück, falls Vorbedingungen nicht erfüllt
// sind, sonst null. (Kein $.exit – das ist in diesem JXA-Kontext nicht
// verfügbar; der Aufrufer beendet sauber per return.)
function preflightReason() {
	const fm = $.NSFileManager.defaultManager;
	if (!fm.fileExistsAtPath(SSD_MOUNT)) return "SSD '2TB_SSD' nicht gemountet.";
	if (!fm.fileExistsAtPath(MUSIC_LIBRARY_PATH)) return `Mediathek-Datei nicht auf SSD (${MUSIC_LIBRARY_PATH}).`;
	let ps = "";
	try { ps = App.doShellScript("/usr/bin/pmset -g ps"); } catch(e) { return "pmset Aufruf fehlgeschlagen."; }
	if (!/AC Power/.test(ps)) return "kein Strom (Akkubetrieb).";
	return null;
}

// Playlists, die niemals angefasst werden (System / read-only / heikel)
const SKIP_PLAYLISTS = new Set([
	"Favourite Songs",
	"Music",
	"Library",
	"Mediathek",
]);

function quotedForm(s) {
	return "'" + String(s).replace(/'/g, "'\\''") + "'";
}

function log(msg) {
	App.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(LOG_FILE)}`);
}

function logError(msg) {
	App.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(ERROR_FILE)}`);
}

function normKey(artist, name) {
	const a = String(artist || "").toLowerCase().trim();
	const n = String(name || "").toLowerCase().trim();
	return `${a}|||${n}`;
}

// 0 = eigener Track (gewinnt), 1 = Apple-Music-Streaming (verliert)
function originRank(cloudStatus) {
	const cs = String(cloudStatus || "").toLowerCase();
	return cs === "subscription" ? 1 : 0;
}

function toMillis(date) {
	if (!date) return Number.POSITIVE_INFINITY;
	try {
		const t = date.getTime();
		return isFinite(t) ? t : Number.POSITIVE_INFINITY;
	} catch(e) {
		return Number.POSITIVE_INFINITY;
	}
}

// Vergleicht zwei Track-Einträge. Gibt < 0 zurück, wenn `a` BLEIBT.
function compareKeep(a, b) {
	if (a.origin !== b.origin) return a.origin - b.origin;          // 0 < 1 → eigener gewinnt
	if (a.added !== b.added) return a.added - b.added;              // älter gewinnt
	return a.index - b.index;                                       // erstes Vorkommen gewinnt
}

function run(argv) {
	const skipReason = preflightReason();
	if (skipReason) {
		try {
			App.doShellScript(`mkdir -p ${quotedForm(LOG_DIR)}`);
			log(`[${new Date().toISOString()}] ⏭ skip: ${skipReason}`);
		} catch(e) {}
		return `⏭ übersprungen: ${skipReason}`;
	}
	const dryRun = (argv || []).indexOf("--dry-run") >= 0;
	const apply = !dryRun;
	const startedAt = new Date();
	log(`--- Duplicate-Scan gestartet: ${startedAt.toLocaleString("de-DE")} (${apply ? "APPLY" : "DRY-RUN"}) ---`);

	// Apple-Event-Timeout großzügig setzen (Default ~60s ist bei vielen Playlists zu kurz)
	try { Music.timeout = 600; } catch(e) {}

	let allPlaylists = [];
	let attempts = 0;
	while (attempts < 3) {
		try {
			allPlaylists = Music.userPlaylists();
			break;
		} catch(e) {
			attempts++;
			logError(`userPlaylists Versuch ${attempts} fehlgeschlagen: ${e.message}`);
			if (attempts >= 3) return `Abbruch: ${e.message}`;
			$.NSThread.sleepForTimeInterval(3);
		}
	}

	let scanned = 0, skipped = 0, totalDupGroups = 0, totalRemoved = 0, totalErrors = 0;

	for (let p = 0; p < allPlaylists.length; p++) {
		const pl = allPlaylists[p];
		let plName;
		try { plName = pl.name(); } catch(e) { continue; }

		// Smart-Playlists überspringen (Inhalt regelbasiert, lässt sich nicht manuell ändern)
		let isSmart = false;
		try { isSmart = pl.smart(); } catch(e) {}
		if (isSmart) { skipped++; log(`⏭  übersprungen (smart): "${plName}"`); continue; }
		if (SKIP_PLAYLISTS.has(plName)) { skipped++; log(`⏭  übersprungen (system): "${plName}"`); continue; }

		// Folder-Playlists überspringen (enthalten andere Playlists, keine Tracks)
		let specialKind = "";
		try { specialKind = String(pl.specialKind() || ""); } catch(e) {}
		if (specialKind.toLowerCase() === "folder") {
			skipped++;
			log(`⏭  übersprungen (folder): "${plName}"`);
			continue;
		}

		// Bulk-Fetch aller relevanten Properties. Wenn EIN Track in der Playlist
		// kaputt ist (verlorene iCloud-Ref, gelöschte Datei, …), schlägt der
		// gesamte Bulk-Fetch mit "Can't get object" fehl → Fallback auf
		// Per-Track-Loop, der kaputte Tracks einzeln überspringt.
		let names = [], artists = [], ids = [], dates = [], cloudStatuses = [];
		let usedFallback = false;
		try {
			names = pl.tracks.name();
			artists = pl.tracks.artist();
			ids = pl.tracks.persistentID();
			dates = pl.tracks.dateAdded();
			cloudStatuses = pl.tracks.cloudStatus();
		} catch(e) {
			usedFallback = true;
			logError(`Bulk-Fetch fehlgeschlagen für "${plName}" (${e.message}) — fallback auf Per-Track-Loop.`);
			let trackList;
			try { trackList = pl.tracks; } catch(e2) {
				logError(`Per-Track-Fallback: tracks-Liste nicht zugreifbar für "${plName}": ${e2.message}`);
				totalErrors++;
				continue;
			}
			let count = 0;
			try { count = trackList.length; } catch(e2) {
				logError(`Per-Track-Fallback: track-count nicht zugreifbar für "${plName}": ${e2.message}`);
				totalErrors++;
				continue;
			}
			let brokenCount = 0;
			// Property-für-Property mit try/catch: einzelne kaputte Tracks
			// hinterlassen `null` an ihrer Stelle und werden später übersprungen.
			for (let i = 0; i < count; i++) {
				const t = trackList[i];
				let n = null, a = null, id = null, d = null, cs = null, broken = false;
				try { n = t.name(); }           catch(e2) { broken = true; }
				try { a = t.artist(); }         catch(e2) { broken = true; }
				try { id = t.persistentID(); }  catch(e2) { broken = true; }
				try { d = t.dateAdded(); }      catch(e2) {}
				try { cs = t.cloudStatus(); }   catch(e2) {}
				if (broken || !id) { brokenCount++; }
				names.push(n); artists.push(a); ids.push(id); dates.push(d); cloudStatuses.push(cs);
			}
			if (brokenCount > 0) {
				logError(`"${plName}": ${brokenCount}/${count} Track(s) nicht lesbar — werden übersprungen.`);
			}
		}
		const trackCount = ids.length;
		if (trackCount === 0) continue;
		scanned++;

		// Gruppieren nach normalisiertem Schlüssel (Artist|||Title)
		const groups = new Map();
		for (let i = 0; i < trackCount; i++) {
			const key = normKey(artists[i], names[i]);
			if (!key || key === "|||") continue;
			const entry = {
				index: i,
				id: ids[i],
				name: names[i],
				artist: artists[i],
				cloud: cloudStatuses[i],
				origin: originRank(cloudStatuses[i]),
				added: toMillis(dates[i]),
			};
			if (!groups.has(key)) groups.set(key, []);
			groups.get(key).push(entry);
		}

		// Duplikate auflösen
		const toDelete = []; // entries; sortiert nach index DESC für sicheres Löschen
		for (const [, entries] of groups) {
			if (entries.length < 2) continue;
			totalDupGroups++;
			// Kopie sortieren: Sieger zuerst
			const sorted = entries.slice().sort(compareKeep);
			const keeper = sorted[0];
			const losers = sorted.slice(1);
			log(`🔁 "${plName}" — ${keeper.artist} – ${keeper.name}: ${entries.length}× vorhanden`);
			log(`    ✓ behalten:  idx=${keeper.index}  cloud=${keeper.cloud || "?"}  added=${new Date(keeper.added).toLocaleString("de-DE")}`);
			for (const l of losers) {
				log(`    ✗ entfernen: idx=${l.index}  cloud=${l.cloud || "?"}  added=${new Date(l.added).toLocaleString("de-DE")}`);
				toDelete.push(l);
			}
		}

		if (toDelete.length === 0) continue;

		if (!apply) {
			log(`   (dry-run: ${toDelete.length} Track(s) in "${plName}" würden entfernt)`);
			continue;
		}

		// Rückwärts löschen, damit sich Indizes nicht verschieben
		toDelete.sort((a, b) => b.index - a.index);
		let removedHere = 0;
		for (const d of toDelete) {
			try {
				Music.delete(pl.tracks[d.index]);
				removedHere++;
			} catch(e) {
				logError(`Löschen fehlgeschlagen "${plName}" idx=${d.index} ${d.artist} – ${d.name}: ${e.message}`);
				totalErrors++;
			}
		}
		totalRemoved += removedHere;
		log(`   → ${removedHere}/${toDelete.length} Track(s) aus "${plName}" entfernt`);
	}

	const summary = `Playlists gescannt: ${scanned} | übersprungen: ${skipped} | Duplikat-Gruppen: ${totalDupGroups} | entfernt: ${totalRemoved} | Fehler: ${totalErrors}` + (apply ? "" : "  (DRY-RUN — nichts gelöscht)");
	log(summary);
	log(`--- Duplicate-Scan beendet: ${new Date().toLocaleString("de-DE")} ---`);
	log("");
	return summary;
}
