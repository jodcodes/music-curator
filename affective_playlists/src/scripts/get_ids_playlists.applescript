-- getUserPlaylists.scpt
on getUserPlaylists()
	try
		tell application "Music"
			set playlistInfo to {}
			
			-- nur Playlists, die der Benutzer erstellt hat
			repeat with p in user playlists
				if (smart of p is false) then
					set end of playlistInfo to {name:name of p, id:persistent ID of p}
				end if
			end repeat
		end tell
		return playlistInfo
	on error errMsg
		return "ERROR: " & errMsg
	end try
end getUserPlaylists

-- Run
on run argv
	return getUserPlaylists()
end run