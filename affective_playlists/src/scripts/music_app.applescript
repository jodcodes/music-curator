-- Music App Utility Functions
-- Basic utilities for checking and accessing the Music app

-- Check if Music app is available
on checkMusicApp()
    try
        tell application "Music"
            return name
        end tell
    on error errMsg
        return false
    end try
end checkMusicApp

-- Check if a playlist exists
on playlistExists(playlistName)
    try
        tell application "Music"
            if (exists playlist playlistName) then
                return true
            else
                return false
            end if
        end tell
    on error
        return false
    end try
end playlistExists

-- Return the result if called directly
checkMusicApp()
