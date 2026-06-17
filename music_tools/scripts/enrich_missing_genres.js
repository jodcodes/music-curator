#!/usr/bin/env osascript -l JavaScript
// ============================================================
// enrich_missing_genres.js (JXA – JavaScript for Automation)
//
// Befüllt fehlende Genre-Tags für Tracks in "Favourite Songs"
// per iTunes Search API (https://itunes.apple.com/search).
//
// Nur Tracks mit LEEREM Genre werden bearbeitet — bestehende Tags
// werden NIE überschrieben. Resumable: bereits versuchte Track-IDs
// werden in state/enrich_genres_state.json gespeichert.
//
// Manuell starten:
//   /usr/bin/osascript -l JavaScript scripts/enrich_missing_genres.js
//
// Nicht im run_all.sh — läuft langsam (~3.5s pro Track, Rate-Limit).
// ============================================================

ObjC.import("Foundation");

const Music = Application("Music");
Music.includeStandardAdditions = true;
const App = Application.currentApplication();
App.includeStandardAdditions = true;

const HOME = $.NSHomeDirectory().js;
const BASE_DIR = `${HOME}/own_repos/music-curator/music_tools`;
const LOG_DIR = `${HOME}/own_repos/music-curator/logs`;
const LOG_FILE = `${LOG_DIR}/enrich_missing_genres.log`;
const ERROR_FILE = `${LOG_DIR}/enrich_missing_genres.err.log`;
const STATE_FILE = `${BASE_DIR}/state/enrich_genres_state.json`;

const REQUEST_DELAY_SEC = 3.5;   // ~17 req/min, unter dem 20/min Apple-Limit
const SAVE_EVERY = 10;            // State alle N Tracks persistieren
const COUNTRY = "de";             // iTunes-Storefront

function quotedForm(s) {
	return "'" + String(s).replace(/'/g, "'\\''") + "'";
}

function log(msg) {
	App.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(LOG_FILE)}`);
}

function logError(msg) {
	App.doShellScript(`echo ${quotedForm(msg)} >> ${quotedForm(ERROR_FILE)}`);
}

function loadState() {
	try {
		const data = $.NSString.stringWithContentsOfFileEncodingError(STATE_FILE, $.NSUTF8StringEncoding, null);
		if (data && data.js) return JSON.parse(data.js);
	} catch(e) {}
	return { tried: [], filled: 0, noMatch: 0, errors: 0, lastRun: null };
}

function saveState(state) {
	const json = JSON.stringify(state, null, 2);
	const nsStr = $.NSString.alloc.initWithUTF8String(json);
	nsStr.writeToFileAtomicallyEncodingError(STATE_FILE, true, $.NSUTF8StringEncoding, null);
}

// Normalisierung für lockeres String-Matching
function normalize(s) {
	if (!s) return "";
	return s
		.toLowerCase()
		.normalize("NFD").replace(/[\u0300-\u036f]/g, "")  // Diakritika weg
		.replace(/\([^)]*\)/g, "")                          // (...) weg
		.replace(/\[[^\]]*\]/g, "")                         // [...] weg
		.replace(/\s*-\s*(remix|edit|mix|version|remastered|remaster|radio edit|original mix).*$/i, "")
		.replace(/feat\.?\s.*$/i, "")
		.replace(/[^\w\s]/g, " ")                           // Sonderzeichen → space
		.replace(/\s+/g, " ")
		.trim();
}

function urlEncode(s) {
	const ns = $.NSString.alloc.initWithUTF8String(s);
	const allowed = $.NSCharacterSet.URLQueryAllowedCharacterSet;
	return ns.stringByAddingPercentEncodingWithAllowedCharacters(allowed).js;
}

function searchItunes(artist, title) {
	const term = `${normalize(artist)} ${normalize(title)}`.trim();
	if (!term) return null;
	const url = `https://itunes.apple.com/search?term=${urlEncode(term)}&entity=song&limit=5&country=${COUNTRY}`;
	let raw;
	try {
		raw = App.doShellScript(`/usr/bin/curl -s --max-time 10 ${quotedForm(url)}`);
	} catch(e) {
		throw new Error(`curl failed: ${e.message}`);
	}
	if (!raw) return null;
	// iTunes liefert bei Rate-Limit / 5xx eine HTML-Fehlerseite statt JSON.
	// Statt mit "JSON parse failed: Unrecognized token '<'" zu crashen,
	// behandeln wir das als "kein Match" und fahren fort.
	const trimmed = raw.trim();
	if (trimmed.startsWith("<") || !trimmed.startsWith("{")) {
		return null;
	}
	let data;
	try {
		data = JSON.parse(raw);
	} catch(e) {
		throw new Error(`JSON parse failed: ${e.message}`);
	}
	if (!data.results || data.results.length === 0) return null;

	// Versuche besten Match aus Top-5 zu finden
	const targetArtist = normalize(artist);
	const targetTitle = normalize(title);
	let best = null;
	let bestScore = 0;
	for (const r of data.results) {
		const rArtist = normalize(r.artistName || "");
		const rTitle = normalize(r.trackName || r.trackCensoredName || "");
		let score = 0;
		if (rArtist === targetArtist) score += 2;
		else if (rArtist.includes(targetArtist) || targetArtist.includes(rArtist)) score += 1;
		if (rTitle === targetTitle) score += 2;
		else if (rTitle.includes(targetTitle) || targetTitle.includes(rTitle)) score += 1;
		if (score > bestScore) { bestScore = score; best = r; }
	}
	if (!best || bestScore < 2) return null; // mindestens ein voller Match nötig
	return {
		genre: best.primaryGenreName,
		matchedArtist: best.artistName,
		matchedTitle: best.trackName,
		score: bestScore
	};
}

function sleep(seconds) {
	$.NSThread.sleepForTimeInterval(seconds);
}

function run(argv) {
	const startedAt = new Date();
	log(`--- Enrichment gestartet: ${startedAt.toLocaleString("de-DE")} ---`);

	const state = loadState();
	const triedSet = new Set(state.tried);

	// Optional: --dry-run flag
	const dryRun = (argv || []).indexOf("--dry-run") >= 0;
	if (dryRun) log("DRY-RUN: schreibe Genres NICHT zurück.");

	// Favourite Songs holen
	const favPlaylist = Music.playlists.whose({name: "Favourite Songs"})[0];

	// Bulk-Fetch aller Properties in einem Apple Event pro Property
	// (~50× schneller als per-Track loop)
	log("Lade Track-Metadaten (Bulk)...");
	const fetchStart = Date.now();
	let genres = [], ids = [], names = [], artists = [], cloudStatuses = [];
	try {
		genres = favPlaylist.tracks.genre();
		ids = favPlaylist.tracks.persistentID();
		names = favPlaylist.tracks.name();
		artists = favPlaylist.tracks.artist();
		cloudStatuses = favPlaylist.tracks.cloudStatus();
	} catch(e) {
		logError(`Bulk-Fetch fehlgeschlagen: ${e.message}`);
		return `Abbruch: Bulk-Fetch fehlgeschlagen (${e.message})`;
	}
	const trackCount = ids.length;
	log(`Bulk-Fetch fertig: ${trackCount} Tracks in ${((Date.now()-fetchStart)/1000).toFixed(1)}s`);

	// Kandidaten ermitteln: leeres Genre, noch nicht versucht,
	// und KEIN Apple-Music-Streaming-Track (cloud status "subscription").
	const candidates = [];
	let skippedSubscription = 0, skippedHasGenre = 0, skippedTried = 0;
	for (let i = 0; i < trackCount; i++) {
		const g = genres[i];
		const id = ids[i];
		const cs = String(cloudStatuses[i] || "").toLowerCase();
		if (g && String(g).trim().length > 0) { skippedHasGenre++; continue; }
		if (cs === "subscription") { skippedSubscription++; continue; }
		if (triedSet.has(id)) { skippedTried++; continue; }
		candidates.push({ index: i, id, name: names[i], artist: artists[i] });
	}

	log(`Tracks insgesamt: ${trackCount} | hat schon Genre: ${skippedHasGenre} | Apple-Music-Streaming (übersprungen): ${skippedSubscription} | bereits versucht: ${skippedTried} | Kandidaten dieser Lauf: ${candidates.length}`);

	let filled = 0, noMatch = 0, errors = 0;

	for (let k = 0; k < candidates.length; k++) {
		const c = candidates[k];
		try {
			const result = searchItunes(c.artist, c.name);
			if (!result) {
				log(`❓ ${c.artist} – ${c.name}: kein Match`);
				noMatch++;
			} else {
				if (!dryRun) {
					try {
						const t = favPlaylist.tracks[c.index];
						t.genre = result.genre;
					} catch(e) {
						logError(`Schreiben fehlgeschlagen ${c.artist} – ${c.name}: ${e.message}`);
						errors++;
						continue;
					}
				}
				log(`✅ ${c.artist} – ${c.name} → ${result.genre}  (Match: ${result.matchedArtist} – ${result.matchedTitle}, score=${result.score})`);
				filled++;
			}
		} catch(e) {
			logError(`API-Fehler bei ${c.artist} – ${c.name}: ${e.message}`);
			errors++;
		}
		triedSet.add(c.id);

		// State periodisch sichern
		if ((k + 1) % SAVE_EVERY === 0) {
			state.tried = Array.from(triedSet);
			state.filled = (state.filled || 0) + filled;
			state.noMatch = (state.noMatch || 0) + noMatch;
			state.errors = (state.errors || 0) + errors;
			state.lastRun = new Date().toISOString();
			saveState(state);
			filled = 0; noMatch = 0; errors = 0;
		}

		// Throttle
		if (k < candidates.length - 1) sleep(REQUEST_DELAY_SEC);
	}

	// Final speichern
	state.tried = Array.from(triedSet);
	state.filled = (state.filled || 0) + filled;
	state.noMatch = (state.noMatch || 0) + noMatch;
	state.errors = (state.errors || 0) + errors;
	state.lastRun = new Date().toISOString();
	saveState(state);

	const summary = `Befüllt: ${state.filled} (gesamt) | kein Match: ${state.noMatch} (gesamt) | Fehler: ${state.errors} (gesamt)`;
	log(summary);
	log(`--- Enrichment beendet: ${new Date().toLocaleString("de-DE")} ---`);
	log("");
	return summary;
}
