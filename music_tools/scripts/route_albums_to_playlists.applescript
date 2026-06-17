-- Mapping von Albumname → Playlistname
property albumPlaylistMap : {¬
	{"DeepDubMinimal", "DeepDubMinimal"}, ¬
	{"Detroit/Chicago/NYGarage", "Detroit/Chicago/NYGarage"}, ¬
	{"Español&Portguês", "Español&Português"}, ¬
	{"HardGroove&Rave", "HardGroove&Rave"}, ¬
	{"Hip-Hop", "Hip-Hop"}, ¬
	{"House&Miscellaneous", "House&Miscellaneous"}, ¬
	{"JazzyHouse", "Jazzy House"}, ¬
	{"latin raptor core", "latin raptor housecore"}, ¬
	{"Mixed", "Mixed"}, ¬
	{"Nu Disco&Funky House", "Nu Disco&Funky House"}, ¬
	{"Prog/Melodic House/Techno", "Prog/Melodic House/Techno"}, ¬
	{"Reggae&Dub", "Reggae&Dub"}, ¬
	{"Soul&Funk", "Soul&Funk"}, ¬
	{"Synth&Micro House", "Synth&Micro House"}, ¬
	{"World", "World"}, ¬
	{"70sPursuit", "70s Pursuit"}, ¬
	{"Acid", "Acid"}, ¬
	{"Disco&Funk", "Disco&Funk"}, ¬
	{"EuroTrance&PopEdits", "EuroTrance&PopEdits"}, ¬
	{"Française", "Française"}, ¬
	{"Jazz", "Jazz"}, ¬
	{"Ol' Skool House", "Ol' Skool House"}, ¬
	{"Synth World", "Synth World"}, ¬
	{"Voicy House", "Voicy House"}, ¬
	{"World House/Techno", "World House/Techno"}, ¬
	{"00s", "00s child"}, ¬
	{"10s for the youth", "10s for the youth"}, ¬
	{"60sPeace", "60sPeace"}, ¬
	{"80s sind die alten 10s", "80s sind die alten 10s"}, ¬
	{"90sRave", "90sRave"}, ¬
	{"90s started lives", "90s started lives"}, ¬
	{"Voicy Techno", "Voicy Techno"}, ¬
	{"Trip-Hop", "Trip-Hop/IDM"}, ¬
	{"Breaks,Jungle,DnB,UKG", "Breaks,Jungle,UKG"}, ¬
	{"Español&Português", "Español&Português"}, ¬
	{"Bass,Ghetto&TechHouse", "Bass,Ghetto&TechHouse"} ¬
		}

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
set musicLibraryPath to "/Volumes/2TB_SSD/Music Library [2025-06-20].musiclibrary"
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
my writeToFile("=== Skriptstart ===", logFile)
my writeToFile("Letzter Lauf: " & (lastRunDate as string), logFile)

set totalConsidered to 0
set totalAdded to 0
set totalAlreadyIn to 0
set totalAlbumsProcessed to 0
set totalAlbumsMissing to 0

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

my writeToFile("📊 Zusammenfassung: " & totalAdded & " hinzugefügt | " & totalAlreadyIn & " bereits drin | " & totalConsidered & " geprüft | " & totalAlbumsProcessed & " Playlists OK | " & totalAlbumsMissing & " Playlists fehlen", logFile)

my saveLastRunDate(current date)
my writeToFile("=== Skriptende ===" & linefeed, logFile)







