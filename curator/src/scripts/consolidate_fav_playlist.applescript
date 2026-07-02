on run argv
    if (count of argv) is not 1 then return "ERROR: playlist name required"
    set playlistName to item 1 of argv
    set mergedCount to 0
    set deletedCount to 0
    set removedDuplicateTracks to 0

    tell application "Music"
        set favMatches to {}
        set matches to every user playlist whose name is playlistName
        repeat with candidate in matches
            try
                if name of parent of candidate is "Fav Songs" then set end of favMatches to contents of candidate
            end try
        end repeat
        if (count of favMatches) is 0 then return "SUCCESS " & playlistName & " missing"

        set keeper to item 1 of favMatches
        if (count of favMatches) > 1 then
            repeat with duplicatePlaylist in items 2 thru -1 of favMatches
                repeat with sourceTrack in tracks of duplicatePlaylist
                    duplicate sourceTrack to keeper
                    set mergedCount to mergedCount + 1
                end repeat
                delete duplicatePlaylist
                set deletedCount to deletedCount + 1
            end repeat
        end if

        set seenPIDs to {}
        set deleteIndexes to {}
        set trackTotal to count of tracks of keeper
        repeat with trackIndex from 1 to trackTotal
            set trackPID to ""
            try
                set trackPID to persistent ID of track trackIndex of keeper
            end try
            if trackPID is not "" then
                if seenPIDs contains trackPID then
                    set beginning of deleteIndexes to trackIndex
                else
                    set end of seenPIDs to trackPID
                end if
            end if
        end repeat
        repeat with deleteIndex in deleteIndexes
            try
                delete track (deleteIndex as integer) of keeper
                set removedDuplicateTracks to removedDuplicateTracks + 1
            end try
        end repeat
    end tell

    return "SUCCESS " & playlistName & " merged=" & mergedCount & " deleted_playlists=" & deletedCount & " removed_duplicate_tracks=" & removedDuplicateTracks
end run
