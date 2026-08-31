-- Mapping von Albumname → Playlistname – geladen aus shared JSON-Config
-- (curator/data/config/album_playlist_map.json)
set jsonPath to (POSIX path of (path to home folder)) & "own_repos/music-curator/curator/data/config/album_playlist_map.json"
set mapOutput to do shell script "/usr/bin/python3 -c \"import json; [print(e['album']+'\\t'+e['playlist']) for e in json.load(open('" & jsonPath & "'))]\""
set albumPlaylistMap to {}
set oldDelims to AppleScript's text item delimiters
set AppleScript's text item delimiters to return
set mapLines to text items of mapOutput
set AppleScript's text item delimiters to tab
repeat with aLine in mapLines
	if aLine is "" then
		exit repeat
	end if
	set tabItems to text items of aLine
	set end of albumPlaylistMap to {item 1 of tabItems, item 2 of tabItems}
end repeat
set AppleScript's text item delimiters to oldDelims

-- Ordner bestimmen, in dem das Skript liegt
set scriptFile to (path to me)

tell application "System Events"
	if class of scriptFile is folder then
		-- Falls das Skript selbst ein Ordner ist (z. B. Script Bundle)
		set scriptFolder to POSIX path of scriptFile
	else
		-- Normales .scpt → Speicherort ist der Container
		set scriptFolder to POSIX path of (container of scriptFile)
	end if
end tell

-- Sicherstellen, dass scriptFolder mit "/" endet, damit Pfade korrekt zusammengesetzt werden
if scriptFolder does not end with "/" then
	set scriptFolder to scriptFolder & "/"
end if

-- Log-/State-Dateien im music-curator/music_tools Repo
-- als Globals, damit sie in den Handlern (loadLastRunDate / saveLastRunDate) sichtbar sind.
global baseDir, logDir, logFile, errorFile, lastRunFile
set baseDir to (POSIX path of (path to home folder)) & "own_repos/music-curator/music_tools/"
set logDir to (POSIX path of (path to home folder)) & "own_repos/music-curator/logs/"
set logFile to (logDir & "route_albums_to_playlists.log")
set errorFile to (logDir & "route_albums_to_playlists.err.log")
set lastRunFile to (baseDir & "state/route_albums_lastRun.txt")

-- ✏️ Schreiben in Datei (legt sie automatisch an)
on writeToFile(logText, filePath)
	do shell script "mkdir -p " & quoted form of (do shell script "dirname " & quoted form of filePath)
	do shell script "touch " & quoted form of filePath
	try
		set f to open for access (POSIX file filePath) with write permission
		write (((current date) as string) & " — " & logText & linefeed) to f starting at eof
		close access f
	on error
		try
			close access (POSIX file filePath)
		end try
	end try
end writeToFile

-- 🕒 Datum laden
on loadLastRunDate()
	global lastRunFile
	try
		set f to open for access (POSIX file lastRunFile)
		set dateString to read f as «class utf8»
		close access f
		return date dateString
	on error
		try
			close access (POSIX file lastRunFile)
		end try
		return date "Saturday, 1. January 2000 at 00:00:00"
	end try
end loadLastRunDate

-- 💾 Datum speichern
on saveLastRunDate(theDate)
	global lastRunFile, errorFile
	try
		do shell script "mkdir -p " & quoted form of (do shell script "dirname " & quoted form of lastRunFile)
		do shell script "touch " & quoted form of lastRunFile
		set f to open for access (POSIX file lastRunFile) with write permission
		set eof of f to 0
		write (theDate as string) to f as «class utf8»
		close access f
	on error errMsg
		try
			close access (POSIX file lastRunFile)
		end try
		my writeToFile("⚠️ saveLastRunDate fehlgeschlagen: " & errMsg, errorFile)
	end try
end saveLastRunDate

-- 🛡 Preflight: SSD gemountet, Mediathek-Datei vorhanden, am Strom
set ssdMount to "/Volumes/2TB_SSD"
set musicLibraryPath to "/Volumes/2TB_SSD/Media (Musik Mediathek)/Music Library [2025-06-20].musiclibrary"
set preflightOK to true
set preflightReason to ""
tell application "System Events"
	if not (exists disk item ssdMount) then
		set preflightOK to false
		set preflightReason to "SSD '2TB_SSD' nicht gemountet."
	else if not (exists disk item musicLibraryPath) then
		set preflightOK to false
		set preflightReason to "Mediathek-Datei nicht auf SSD (" & musicLibraryPath & ")."
	end if
end tell
if preflightOK then
	try
		set psOut to do shell script "/usr/bin/pmset -g ps"
		if psOut does not contain "AC Power" then
			set preflightOK to false
			set preflightReason to "kein Strom (Akkubetrieb)."
		end if
	on error
		set preflightOK to false
		set preflightReason to "pmset Aufruf fehlgeschlagen."
	end try
end if
if not preflightOK then
	my writeToFile("⏭ skip: " & preflightReason, logFile)
	return
end if

-- 🎵 Hauptlogik
set lastRunDate to loadLastRunDate()
my writeToFile("=== Skriptstart [START] ===", logFile)
my writeToFile("Letzter Lauf: " & (lastRunDate as string), logFile)

set totalConsidered to 0
set totalAdded to 0
set totalAlreadyIn to 0
set totalAlbumsProcessed to 0
set totalAlbumsMissing to 0
set totalTrackErrors to 0

tell application "Music"
	repeat with apPair in albumPlaylistMap
		set albumName to item 1 of apPair
		set playlistName to item 2 of apPair
		
		try
			set targetPlaylist to user playlist playlistName
		on error
			my writeToFile("⚠️ Playlist '" & playlistName & "' nicht gefunden.", errorFile)
			set totalAlbumsMissing to totalAlbumsMissing + 1
			set targetPlaylist to missing value
		end try
		
		if targetPlaylist is not missing value then
			set totalAlbumsProcessed to totalAlbumsProcessed + 1
			set newTracks to (every track of library playlist 1 whose album is albumName and date added > lastRunDate)
			set newTrackCount to count of newTracks
			set addedHere to 0
			set alreadyHere to 0
			
			if newTrackCount > 0 then
				my writeToFile("🔍 Album '" & albumName & "' → " & playlistName & ": " & newTrackCount & " neue Track(s) seit letztem Lauf", logFile)
			end if
			
			set totalConsidered to totalConsidered + newTrackCount
			
			repeat with t in newTracks
				try
					if (database ID of t) is not in (database ID of every track of targetPlaylist) then
						duplicate t to targetPlaylist
						my writeToFile("➕ '" & name of t & "' → " & playlistName, logFile)
						set addedHere to addedHere + 1
					else
						set alreadyHere to alreadyHere + 1
					end if
				on error errMsg
					my writeToFile("⚠️ Track-Fehler bei '" & playlistName & "': " & errMsg, errorFile)
					set totalTrackErrors to totalTrackErrors + 1
				end try
			end repeat
			
			set totalAdded to totalAdded + addedHere
			set totalAlreadyIn to totalAlreadyIn + alreadyHere
			
			if newTrackCount > 0 then
				my writeToFile("   ↳ hinzugefügt: " & addedHere & " | bereits drin: " & alreadyHere, logFile)
			end if
		end if
	end repeat
end tell

my writeToFile("📊 Zusammenfassung: " & totalAdded & " hinzugefügt | " & totalAlreadyIn & " bereits drin | " & totalConsidered & " geprüft | " & totalAlbumsProcessed & " Playlists OK | " & totalAlbumsMissing & " Playlists fehlen | " & totalTrackErrors & " Track-Fehler", logFile)

-- Checkpoint nur bei vollständigem Erfolg verschieben: eine fehlende Ziel-
-- Playlist oder ein fehlgeschlagener Track dürfen die betroffene Arbeit nie
-- dauerhaft verlieren. Bleibt lastRunDate stehen, greift sie beim nächsten
-- Lauf erneut (date added > lastRunDate).
if totalAlbumsMissing is 0 and totalTrackErrors is 0 then
	my saveLastRunDate(current date)
	my writeToFile("=== Skriptende [SUCCESS] ===" & linefeed, logFile)
else
	my writeToFile("=== Skriptende [FAIL] " & totalAlbumsMissing & " Playlist(s) fehlen, " & totalTrackErrors & " Track-Fehler — Checkpoint NICHT verschoben ===" & linefeed, logFile)
	error "route_albums_to_playlists: " & totalAlbumsMissing & " missing playlist(s), " & totalTrackErrors & " track error(s) — see " & errorFile number 1
end if






