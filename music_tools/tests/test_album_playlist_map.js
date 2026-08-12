#!/usr/bin/env osascript -l JavaScript
// Test: album_playlist_map.json wird korrekt geladen und enthält alle Einträge

ObjC.import("Foundation");

const HOME = $.NSHomeDirectory().js;
const JSON_PATH = `${HOME}/own_repos/music-curator/curator/data/config/album_playlist_map.json`;

const nsStr = $.NSString.stringWithContentsOfFileEncodingError(JSON_PATH, $.NSUTF8StringEncoding, null);
if (!nsStr) {
	console.log("FAIL: Datei nicht gefunden: " + JSON_PATH);
	$.exit(1);
}

const map = JSON.parse(nsStr.js);

if (!Array.isArray(map) || map.length === 0) {
	console.log("FAIL: Kein Array oder leer");
	$.exit(1);
}

let pass = 0, fail = 0;
for (const entry of map) {
	if (!entry.album || !entry.playlist) {
		console.log("FAIL: Eintrag ohne album/playlist: " + JSON.stringify(entry));
		fail++;
	} else {
		pass++;
	}
}

// Spot-Checks für kritische Einträge
const checks = [
	["Trip-Hop", "Trip-Hop/IDM"],
	["00s", "00s child"],
	["latin raptor core", "latin raptor housecore"],
	["Español&Português", "Español&Português"],
];
for (const [album, playlist] of checks) {
	const found = map.some(e => e.album === album && e.playlist === playlist);
	if (found) { pass++; } else {
		console.log(`FAIL: "${album}" -> "${playlist}" nicht gefunden`);
		fail++;
	}
}

// Verwaiste Einträge dürfen NICHT mehr im Map stehen
const removed = ["Español&Portguês", "JazzyHouse"];
for (const album of removed) {
	const found = map.some(e => e.album === album);
	if (!found) { pass++; } else {
		console.log(`FAIL: verwaister Eintrag "${album}" sollte entfernt sein`);
		fail++;
	}
}

console.log(`${pass} passed, ${fail} failed, ${map.length} entries`);
if (fail > 0) throw new Error(`${fail} test(s) failed`);
