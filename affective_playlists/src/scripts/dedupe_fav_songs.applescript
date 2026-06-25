on run argv
    set dryRun to false
    if (count of argv) > 0 then
        if item 1 of argv is "--dry-run" then set dryRun to true
    end if

    set scannedCount to 0
    set duplicateCount to 0
    set removedCount to 0
    set ambiguousCount to 0

    tell application "Music"
        set playlistNames to {"African & World", "Alternative & Indie", "Ambient", "Blues", "Breakbeat/Jungle", "Classical", "Disco", "Electronic", "Folk & Singer-Songwriter", "Funk", "Hip Hop & RnB", "House", "IDM", "Jazz", "Latin & Brasileiro", "Lounge", "Pop", "Rock", "Sonstige", "Soul", "Soundtrack", "Techno"}

        repeat with playlistName in playlistNames
            set matches to every user playlist whose name is (playlistName as text)
            if (count of matches) is 0 then
                -- skip missing generated playlist
            else if (count of matches) > 1 then
                set ambiguousCount to ambiguousCount + 1
                set targetPlaylist to item 1 of matches
                repeat with duplicatePlaylist in items 2 thru -1 of matches
                    repeat with sourceTrack in tracks of duplicatePlaylist
                        set trackPID to ""
                        try
                            set trackPID to persistent ID of sourceTrack
                        end try
                        if trackPID is not "" then
                            if my targetHasPID(targetPlaylist, trackPID) then
                                set duplicateCount to duplicateCount + 1
                            else
                                if dryRun is false then duplicate sourceTrack to targetPlaylist
                            end if
                        end if
                    end repeat
                    if dryRun is false then delete duplicatePlaylist
                end repeat
            else
                set targetPlaylist to item 1 of matches
                set scannedCount to scannedCount + 1
                set seenPIDs to {}
                set deleteIndexes to {}
                set trackTotal to count of tracks of targetPlaylist
                repeat with trackIndex from 1 to trackTotal
                    set trackPID to ""
                    try
                        set trackPID to persistent ID of track trackIndex of targetPlaylist
                    end try
                    if trackPID is not "" then
                        if seenPIDs contains trackPID then
                            set duplicateCount to duplicateCount + 1
                            set beginning of deleteIndexes to trackIndex
                        else
                            set end of seenPIDs to trackPID
                        end if
                    end if
                end repeat

                if dryRun is false then
                    repeat with deleteIndex in deleteIndexes
                        try
                            delete track (deleteIndex as integer) of targetPlaylist
                            set removedCount to removedCount + 1
                        end try
                    end repeat
                end if
            end if
        end repeat
    end tell

    if dryRun then
        return "SUCCESS scanned=" & scannedCount & " ambiguous=" & ambiguousCount & " duplicates=" & duplicateCount & " removed=0 dry_run=true"
    end if
    return "SUCCESS scanned=" & scannedCount & " ambiguous=" & ambiguousCount & " duplicates=" & duplicateCount & " removed=" & removedCount
end run

on targetHasPID(targetPlaylist, trackPID)
    tell application "Music"
        try
            set matches to every track of targetPlaylist whose persistent ID is trackPID
            return (count of matches) > 0
        end try
    end tell
    return false
end targetHasPID
