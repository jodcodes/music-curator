-- Move Playlist to Folder by Persistent IDs
on run argv
    if (count of argv) < 2 then
        return "ERROR: Arguments required: playlistID folderID"
    end if
    
    set playlistID to item 1 of argv
    set folderID to item 2 of argv
    
    tell application "Music"
        try
            -- Playlist per PID abrufen
            set thePL to first playlist whose persistent ID is playlistID
            
            -- Zielordner per PID abrufen
            set targetFolder to first playlist whose persistent ID is folderID
            
            -- Playlist verschieben mit move Befehl
            move thePL to targetFolder
            
            return "SUCCESS: Playlist moved"
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
end run