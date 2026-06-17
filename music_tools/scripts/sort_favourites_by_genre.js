#!/usr/bin/env osascript -l JavaScript
// ============================================================
// sort_favourites_by_genre.js (JXA – JavaScript for Automation)
// Holt alle Tracks aus "Favourite Songs" in Apple Music
// und sortiert sie nach Genre in 11 ♥ <Kategorie> Playlisten.
// ============================================================

ObjC.import("Foundation");

const Music = Application("Music");
Music.includeStandardAdditions = true;
// AppleEvent-Timeout hochsetzen (Default 60s reicht bei großen Bibliotheken nicht)
try { Music.timeout = 600; } catch(e) {}

const HOME = $.NSHomeDirectory().js;
const BASE_DIR = `${HOME}/own_repos/music-curator/music_tools`;
const LOG_DIR = `${HOME}/own_repos/music-curator/logs`;
const LOG_FILE = `${LOG_DIR}/sort_favourites_by_genre.log`;
const ERROR_FILE = `${LOG_DIR}/sort_favourites_by_genre.err.log`;

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
	const app = Application.currentApplication();
	app.includeStandardAdditions = true;
	try { ps = app.doShellScript("/usr/bin/pmset -g ps"); } catch(e) { return "pmset Aufruf fehlgeschlagen."; }
	if (!/AC Power/.test(ps)) return "kein Strom (Akkubetrieb).";
	return null;
}

function log(msg) {
	const app = Application.currentApplication();
	app.includeStandardAdditions = true;
	app.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(LOG_FILE)}`);
}

function logError(msg) {
	const app = Application.currentApplication();
	app.includeStandardAdditions = true;
	app.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(ERROR_FILE)}`);
}

function quotedForm(s) {
	return "'" + s.replace(/'/g, "'\\''") + "'";
}

// ============================================================
// Genre-Klassifikation – 1:1-Port von affective_playlists
// (src/curation_models.py -> normalize_fav_genre_label).
// Hält die Fav-Songs-Genres in beiden Repos identisch.
// Reihenfolge der Regeln ist relevant (erste Übereinstimmung gewinnt).
// ============================================================

// Entspricht _genre_search_text aus curation_models.py
function genreSearchText(genre) {
	let t = genre.replace(/_/g, " ").replace(/-/g, " ").trim().toLowerCase();
	return t.replace(/\s+/g, " ");
}

// Entspricht normalize_fav_genre_label aus curation_models.py
function genreCategory(genre) {
	if (!genre) return "Sonstige";
	const text = genreSearchText(genre);
	if (!text) return "Sonstige";

	if (/\bhouse\b/.test(text)) return "House";
	if (/\btechno\b/.test(text)) return "Techno";
	if (/\bbreakbeat\b|jungle|drum.n.bass/.test(text)) return "Breakbeat/Jungle";
	if (/\bidm\b|experimental/.test(text)) return "IDM";
	if (/trip hop|triphop/.test(text)) return "Trip-Hop";
	if (/\bdisco\b/.test(text)) return "Disco";
	if (/\bfunk\b/.test(text)) return "Funk";
	if (/soul/.test(text)) return "Soul";
	if (/\bjazz\b|fusion/.test(text)) return "Jazz";
	if (/\bblues\b/.test(text)) return "Blues";
	if (/\balt\b|alternative|indie|grunge|punk|new wave|psychedelic|psychedelisch|kraut|prog rock|art rock|british invasion|adult alternative/.test(text)) return "Alternative & Indie";
	if (/classical|klassik|klassisch|neoclassical|baroque|barock/.test(text)) return "Classical";
	if (/rock|metal|surf|hardcore/.test(text)) return "Rock";
	if (/\bpop\b|lounge|easy listening|new age|christmas|inspirational|schlager|vocal/.test(text)) {
		if (text.indexOf("lounge") !== -1) return "Lounge";
		return "Pop";
	}
	if (/folk|singer|songwriter|country|traditional folk/.test(text)) return "Folk & Singer-Songwriter";
	if (/ambient/.test(text)) return "Ambient";
	if (/electro|electronica|dance|trance|downtempo|garage|bass|speed|deep|post club|rave|edm|fitness|workout/.test(text)) return "Electronic";
	if (/hip|hop|rap|r&b|rnb|r & b|r and b|dope/.test(text)) return "Hip Hop & RnB";
	if (/latin|latino|latina|pagode|tropical|baile|mpb|bossa|brazilian|brasilianisch|balada|bolero|rumba|mexicana|mexiko|south america|caribbean|karibik|urbano|reggae|dancehall|cuban|salsa|flamenco|samba/.test(text)) return "Latin & Brasileiro";
	if (/afro|african|afrikanische|afrobeats|highlife|world|welt|turkish|halk|farsi|bollywood|j pop|kayokyoku|worldwide/.test(text)) return "African & World";
	if (/soundtrack|soundtracks|score|originalfilm|tv soundtrack/.test(text)) return "Soundtrack";
	if (text === "other" || text === "sonstige") return "Sonstige";

	return "Sonstige";
}

function getOrCreatePlaylist(name) {
	const existing = Music.userPlaylists.whose({name: name});
	if (existing.length > 0) {
		return existing[0];
	}
	return Music.UserPlaylist({name: name}).make();
}

// Einmalige Migration: alte Playlist-Namen "♥ Faved – X" → "♥ X" umbenennen
function migrateFavedPrefix() {
	const OLD_PREFIX = "♥ Faved – ";
	const NEW_PREFIX = "♥ ";
	const all = Music.userPlaylists();
	const existingNames = new Set(all.map(p => { try { return p.name(); } catch(e) { return ""; } }));
	for (let i = 0; i < all.length; i++) {
		const pl = all[i];
		let n;
		try { n = pl.name(); } catch(e) { continue; }
		if (!n.startsWith(OLD_PREFIX)) continue;
		const newName = NEW_PREFIX + n.substring(OLD_PREFIX.length);
		if (existingNames.has(newName)) {
			log(`Migration übersprungen (Konflikt): "${n}" — "${newName}" existiert bereits`);
			continue;
		}
		try {
			pl.name = newName;
			existingNames.add(newName);
			log(`Migration: "${n}" → "${newName}"`);
		} catch(e) {
			logError(`Migration fehlgeschlagen für "${n}": ${e.message}`);
		}
	}
}

function run() {
	const skipReason = preflightReason();
	if (skipReason) {
		try {
			const app = Application.currentApplication();
			app.includeStandardAdditions = true;
			app.doShellScript(`mkdir -p ${quotedForm(LOG_DIR)}`);
			log(`[${new Date().toISOString()}] ⏭ skip: ${skipReason}`);
		} catch(e) {}
		return `⏭ übersprungen: ${skipReason}`;
	}
	const now = new Date();
	const nowStr = now.toLocaleString("de-DE");
	log(`--- Sync gestartet: ${nowStr} ---`);

	const PREFIX = "♥ ";
	// Kategorien = Fav-Songs-Genres aus affective_playlists
	// (curation_models.normalize_fav_genre_label). Reihenfolge = Anzeige.
	const categories = [
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
	];

	// === Migration alter Playlist-Namen "♥ Faved – X" → "♥ X" ===
	migrateFavedPrefix();

	// === Genre-Playlisten vorbereiten + existierende Track-IDs cachen ===
	const playlists = {};
	for (const cat of categories) {
		const pl = getOrCreatePlaylist(PREFIX + cat);
		let ids = [];
		let keys = new Set();
		try {
			ids = pl.tracks.persistentID();
			const names = pl.tracks.name();
			const artists = pl.tracks.artist();
			for (let j = 0; j < names.length; j++) {
				keys.add(`${(artists[j] || "").toLowerCase()}|||${(names[j] || "").toLowerCase()}`);
			}
		} catch(e) {}
		playlists[cat] = { playlist: pl, existingIDs: new Set(ids), existingKeys: keys };
	}

	// === Cleanup-Pass: Tracks aus falschen ♥-Playlists entfernen ===
	// Für jeden Track in jeder ♥-Playlist: wenn Genre nicht (mehr) zur Kategorie
	// dieser Playlist passt, Track aus der Playlist entfernen.
	// Der Add-Loop unten packt ihn dann in die richtige.
	log("Cleanup: prüfe ♥-Playlists auf falsche Kategorisierung...");
	let cleanupRemoved = 0;
	for (const cat of categories) {
		const target = playlists[cat];
		const pl = target.playlist;
		let pGenres = [], pIds = [], pNames = [], pArtists = [];
		try {
			pGenres = pl.tracks.genre();
			pIds = pl.tracks.persistentID();
			pNames = pl.tracks.name();
			pArtists = pl.tracks.artist();
		} catch(e) { continue; }

		// Rückwärts iterieren, damit Index-Verschiebung beim Löschen nicht stört
		for (let j = pGenres.length - 1; j >= 0; j--) {
			const correctCat = genreCategory(pGenres[j]);
			if (correctCat === cat) continue;
			try {
				Music.delete(pl.tracks[j]);
				target.existingIDs.delete(pIds[j]);
				target.existingKeys.delete(`${(pArtists[j]||"").toLowerCase()}|||${(pNames[j]||"").toLowerCase()}`);
				cleanupRemoved++;
				log(`🔄 ${pArtists[j]} – ${pNames[j]}  [${pGenres[j] || "?"}]: aus "${PREFIX + cat}" entfernt (gehört nach "${PREFIX + correctCat}")`);
			} catch(e) {
				logError(`Cleanup-Fehler ${pArtists[j]} – ${pNames[j]}: ${e.message}`);
			}
		}
	}
	log(`Cleanup fertig: ${cleanupRemoved} Tracks aus falschen Playlists entfernt`);

	// Favourite Songs laden
	const favPlaylist = Music.playlists.whose({name: "Favourite Songs"})[0];
	const trackCount = favPlaylist.tracks.length;
	log(`Favourite Songs Tracks: ${trackCount}`);

	let added = 0, skipped = 0, errors = 0;

	for (let i = 0; i < trackCount; i++) {
		try {
			const t = favPlaylist.tracks[i];
			const trackName = t.name();
			const trackArtist = t.artist();
			const trackGenre = t.genre();
			const trackID = t.persistentID();
			const trackKey = `${(trackArtist || "").toLowerCase()}|||${(trackName || "").toLowerCase()}`;

			const category = genreCategory(trackGenre);
			const target = playlists[category];
			if (!target) continue;

			if (target.existingIDs.has(trackID) || target.existingKeys.has(trackKey)) {
				skipped++;
			} else {
				try {
					Music.duplicate(t, {to: target.playlist});
				} catch(e) {
					try {
						Music.add([t], {to: target.playlist});
					} catch(e2) {
						logError(`ERROR bei Track: ${trackName} – ${e2.message}`);
						errors++;
					}
				}
				target.existingIDs.add(trackID);
				target.existingKeys.add(trackKey);
				added++;
				log(`➕ ${trackArtist} – ${trackName}  [${trackGenre || "?"}] → ${PREFIX + category}`);
			}
		} catch(e) {
			errors++;
			try { logError(`ERROR: ${e.message}`); } catch(e3) {}
		}
	}

	const summary = `Hinzugefügt: ${added} | Übersprungen: ${skipped} | Cleanup-Entfernt: ${cleanupRemoved} | Fehler: ${errors}`;
	log(summary);
	log(`--- Sync beendet: ${new Date().toLocaleString("de-DE")} ---`);
	log("");

	return summary;
}
