tell application "Music"
    set folderInfo to {}
    set allFolders to every folder playlist
    
    repeat with f in allFolders
        set end of folderInfo to {name:name of f, id:persistent ID of f}
    end repeat
end tell

return folderInfo