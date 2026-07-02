-- getPlaylistTracksJSON_byPID.scpt
on getPlaylistTracksByPID(playlistPID)
	try
		if (count of playlistPID) is 0 then
			return "ERROR: Playlist persistent ID required"
		end if
		
		tell application "Music"
			-- Playlist per PID finden
			set p to first playlist whose persistent ID is playlistPID
			
			set pid to persistent ID of p
			set trackList to {}
			
			repeat with t in tracks of p
				-- Check cloud status: only process uploaded or matched tracks
				set cloudStatus to cloud status of t
				if cloudStatus is uploaded or cloudStatus is matched then
					set tname to name of t
					if tname is missing value then set tname to ""
					
					set tartist to artist of t
					if tartist is missing value then set tartist to ""
					
					set talbum to album of t
					if talbum is missing value then set talbum to ""
					
					set tgenre to genre of t
					if tgenre is missing value then set tgenre to ""
					
					set tbpm to bpm of t
					if tbpm is missing value then set tbpm to ""
					
					set tyear to year of t
					if tyear is missing value then set tyear to ""
					
					set tcomposer to composer of t
					if tcomposer is missing value then set tcomposer to ""
					
					set tduration to duration of t
					if tduration is missing value then set tduration to ""
					
					-- Get location (file path) as POSIX path
					set tlocation to ""
					try
						tell application "Music"
							set tfile to (location of t)
							if tfile is not missing value then
								set tlocation to (POSIX path of tfile)
							end if
						end tell
					end try
					if tlocation is missing value then set tlocation to ""
					
					-- Convert cloud status constant to text for transmission
					set tcloudStatus to ""
					if cloudStatus is uploaded then
						set tcloudStatus to "uploaded"
					else if cloudStatus is matched then
						set tcloudStatus to "matched"
					end if
					
					-- Track als Record (JSON-ähnlich)
					set end of trackList to {name:tname, id:(persistent ID of t), artist:tartist, album:talbum, genre:tgenre, bpm:tbpm, year:tyear, composer:tcomposer, duration:tduration, cloudStatus:tcloudStatus, filepath:tlocation}
				end if
			end repeat
		end tell
		
		return trackList
	on error errMsg
		return "ERROR: " & errMsg
	end try
end getPlaylistTracksByPID

-- Run
on run argv
	if (count of argv) is 0 then
		return "ERROR: Playlist persistent ID required"
	else
		return getPlaylistTracksByPID(item 1 of argv)
	end if
end run