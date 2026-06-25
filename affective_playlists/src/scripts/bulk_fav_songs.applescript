on run argv
    if (count of argv) is not 1 then return "ERROR: data file required"
    set dataPath to item 1 of argv
    set dataText to read POSIX file dataPath as «class utf8»
    set rows to paragraphs of dataText
    set copiedCount to 0
    set skippedCount to 0
    set missingCount to 0

    tell application "Music"
        set favPlaylist to playlist "Favourite Songs"
        set rootFolder to my ensureRootFolder("Fav Songs")

        repeat with rowText in rows
            set rowValue to rowText as text
            if rowValue is "" then
                -- skip empty line
            else
                set fields to my splitText(rowValue, tab)
                if (count of fields) ≥ 2 then
                    set trackPID to item 1 of fields
                    set playlistName to item 2 of fields
                    set sourceTrack to my firstTrackByPersistentID(favPlaylist, trackPID)
                    if sourceTrack is missing value then
                        set missingCount to missingCount + 1
                    else
                        set targetPlaylist to my ensureRootPlaylist(rootFolder, playlistName)
                        if my targetHasPID(targetPlaylist, trackPID) then
                            set skippedCount to skippedCount + 1
                        else
                            duplicate sourceTrack to targetPlaylist
                            set copiedCount to copiedCount + 1
                        end if
                    end if
                end if
            end if
        end repeat
    end tell

    return "SUCCESS copied=" & copiedCount & " skipped=" & skippedCount & " missing=" & missingCount
end run

on splitText(sourceText, delimiterText)
    set oldDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to delimiterText
    set textItems to text items of sourceText
    set AppleScript's text item delimiters to oldDelimiters
    return textItems
end splitText

on ensureRootFolder(rootName)
    tell application "Music"
        set matches to every folder playlist whose name is rootName
        if (count of matches) > 1 then error "Ambiguous root folder " & rootName
        if (count of matches) is 1 then return item 1 of matches
        make new folder playlist with properties {name:rootName}
        set matches to every folder playlist whose name is rootName
        if (count of matches) is 0 then error "Could not create folder " & rootName
        if (count of matches) > 1 then error "Ambiguous root folder " & rootName
        return item 1 of matches
    end tell
end ensureRootFolder

on ensureRootPlaylist(rootFolder, playlistName)
    tell application "Music"
        set foundPlaylist to missing value
        set foundCount to 0
        set matches to every user playlist whose name is playlistName
        repeat with candidate in matches
            try
                if name of parent of candidate is "Fav Songs" then
                    set foundPlaylist to contents of candidate
                    set foundCount to foundCount + 1
                end if
            end try
        end repeat
        if foundCount > 1 then return foundPlaylist
        if foundCount is 1 then return foundPlaylist
        return make new user playlist at rootFolder with properties {name:playlistName}
    end tell
end ensureRootPlaylist

on firstTrackByPersistentID(sourcePlaylist, trackPID)
    tell application "Music"
        try
            set matches to every track of sourcePlaylist whose persistent ID is trackPID
            if (count of matches) > 0 then return item 1 of matches
        end try
    end tell
    return missing value
end firstTrackByPersistentID

on targetHasPID(targetPlaylist, trackPID)
    tell application "Music"
        try
            set matches to every track of targetPlaylist whose persistent ID is trackPID
            return (count of matches) > 0
        end try
    end tell
    return false
end targetHasPID
