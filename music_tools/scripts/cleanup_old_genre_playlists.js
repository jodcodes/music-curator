#!/usr/bin/env osascript -l JavaScript
// ============================================================
// cleanup_old_genre_playlists.js (JXA – JavaScript for Automation)
//
// Löscht veraltete "♥ <Kategorie>" Playlisten, deren Name nicht
// (mehr) zur aktuellen Genre-Taxonomie von sort_favourites_by_genre.js
// passt (z. B. "♥ Pop & Lounge", "♥ Jazz & Blues", "♥ Hip-Hop",
// "♥ Disco/Funk/Soul", "♥ Country", "♥ World", "♥ Other").
//
// Es werden NUR Playlisten mit dem Präfix "♥ " betrachtet. Alle
// anderen Playlisten, Smart-Playlisten, Ordner und System-Playlisten
// bleiben unangetastet.
//
// Standard: DRY-RUN (zeigt nur, was gelöscht WÜRDE). Tatsächliches
// Löschen nur mit --apply. Die Tracks der alten Playlisten stammen
// aus "Favourite Songs" und wurden vom Sorter bereits in die neuen
// Kategorien einsortiert – beim Löschen geht also nichts verloren.
//
// Manuell starten:
//   /usr/bin/osascript -l JavaScript scripts/cleanup_old_genre_playlists.js          # dry-run
//   /usr/bin/osascript -l JavaScript scripts/cleanup_old_genre_playlists.js --apply  # löscht
// ============================================================

ObjC.import("Foundation");

const Music = Application("Music");
Music.includeStandardAdditions = true;
const App = Application.currentApplication();
App.includeStandardAdditions = true;
try { Music.timeout = 600; } catch(e) {}

const HOME = $.NSHomeDirectory().js;
const LOG_DIR = `${HOME}/own_repos/music-curator/logs`;
const LOG_FILE = `${LOG_DIR}/cleanup_old_genre_playlists.log`;
const ERROR_FILE = `${LOG_DIR}/cleanup_old_genre_playlists.err.log`;

// --- Preflight: SSD gemountet, Mediathek-Datei vorhanden, am Strom ---
const SSD_MOUNT = "/Volumes/2TB_SSD";
const MUSIC_LIBRARY_PATH = `${SSD_MOUNT}/Music Library [2025-06-20].musiclibrary`;

const PREFIX = "♥ ";

// Aktuell gültige Kategorien – MUSS mit sort_favourites_by_genre.js übereinstimmen.
const VALID_CATEGORIES = new Set([
	"Pop",
	"Lounge",
	"Rock",
	"Alternative & Indie",
	"Folk & Singer-Songwriter",
	"Hip Hop & RnB",
	"Trip-Hop",
	"Electronic",
	"House",
	"Techno",
	"Breakbeat/Jungle",
	"IDM",
	"Ambient",
	"Disco",
	"Funk",
	"Soul",
	"Jazz",
	"Blues",
	"Classical",
	"Latin & Brasileiro",
	"African & World",
	"Soundtrack",
	"Sonstige"
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

function run(argv) {
	const skipReason = preflightReason();
	if (skipReason) {
		try {
			App.doShellScript(`mkdir -p ${quotedForm(LOG_DIR)}`);
			log(`[${new Date().toISOString()}] ⏭ skip: ${skipReason}`);
		} catch(e) {}
		return `⏭ übersprungen: ${skipReason}`;
	}
	const apply = (argv || []).indexOf("--apply") >= 0;
	const startedAt = new Date();
	log(`--- Cleanup gestartet: ${startedAt.toLocaleString("de-DE")} (${apply ? "APPLY" : "DRY-RUN"}) ---`);

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

	// Erst Kandidaten sammeln (Name + Track-Anzahl), dann rückwärts löschen
	// (rückwärts, damit Index-Verschiebung beim Löschen nicht stört).
	const candidates = [];
	for (let p = 0; p < allPlaylists.length; p++) {
		const pl = allPlaylists[p];
		let plName;
		try { plName = pl.name(); } catch(e) { continue; }

		// Nur "♥ " Playlisten betrachten
		if (!plName.startsWith(PREFIX)) continue;

		// Smart-Playlisten und Ordner nie löschen
		let isSmart = false;
		try { isSmart = pl.smart(); } catch(e) {}
		if (isSmart) { log(`⏭  übersprungen (smart): "${plName}"`); continue; }
		let specialKind = "";
		try { specialKind = String(pl.specialKind() || ""); } catch(e) {}
		if (specialKind.toLowerCase() === "folder") { log(`⏭  übersprungen (folder): "${plName}"`); continue; }

		const category = plName.substring(PREFIX.length);
		if (VALID_CATEGORIES.has(category)) continue; // gültig → behalten

		let trackCount = "?";
		try { trackCount = pl.tracks.length; } catch(e) {}
		candidates.push({ index: p, name: plName, tracks: trackCount });
	}

	if (candidates.length === 0) {
		const msg = "Keine veralteten ♥-Playlisten gefunden – nichts zu tun.";
		log(msg);
		log(`--- Cleanup beendet: ${new Date().toLocaleString("de-DE")} ---`);
		log("");
		return msg;
	}

	log(`Gefundene veraltete ♥-Playlisten: ${candidates.length}`);
	for (const c of candidates) {
		log(`   • "${c.name}" (${c.tracks} Tracks)`);
	}

	let deleted = 0, errors = 0;
	if (apply) {
		// Rückwärts löschen, damit frühere Index-Referenzen gültig bleiben
		for (let i = candidates.length - 1; i >= 0; i--) {
			const c = candidates[i];
			try {
				Music.delete(allPlaylists[c.index]);
				deleted++;
				log(`🗑  gelöscht: "${c.name}"`);
			} catch(e) {
				errors++;
				logError(`Löschen fehlgeschlagen für "${c.name}": ${e.message}`);
			}
		}
	} else {
		log(`(dry-run: ${candidates.length} Playlist(en) würden gelöscht – mit --apply ausführen)`);
	}

	const summary = apply
		? `Gelöscht: ${deleted} | Fehler: ${errors}`
		: `Dry-Run: ${candidates.length} Playlist(en) zum Löschen markiert (mit --apply ausführen)`;
	log(summary);
	log(`--- Cleanup beendet: ${new Date().toLocaleString("de-DE")} ---`);
	log("");
	return summary;
}
