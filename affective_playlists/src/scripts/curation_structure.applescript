on run argv
    if (count of argv) < 2 then
        return "ERROR: action and path required"
    end if

    set actionName to item 1 of argv
    set pathArgs to items 2 thru -1 of argv

    try
        if actionName is "ensure_folder" then
            return my ensureFolder(pathArgs)
        else if actionName is "ensure_playlist" then
            return my ensurePlaylist(pathArgs)
        else if actionName is "copy_track" then
            return my copyTrack(pathArgs)
        end if
        return "ERROR: unsupported action: " & actionName
    on error errMsg
        return "ERROR: " & errMsg
    end try
end run

on ensureFolder(pathArgs)
    if (count of pathArgs) is 1 then
        set rootName to item 1 of pathArgs
        my ensureRootFolder(rootName)
        return "SUCCESS: folder ensured " & rootName
    else if (count of pathArgs) is 2 then
        set rootName to item 1 of pathArgs
        set genreName to item 2 of pathArgs
        my ensureGenreFolder(rootName, genreName)
        return "SUCCESS: folder ensured " & rootName & " / " & genreName
    end if
    return "ERROR: ensure_folder requires root or root/genre path"
end ensureFolder

on ensurePlaylist(pathArgs)
    if (count of pathArgs) is not 3 then
        return "ERROR: ensure_playlist requires root/genre/playlist path"
    end if
    set rootName to item 1 of pathArgs
    set genreName to item 2 of pathArgs
    set playlistName to item 3 of pathArgs
    my ensureTargetPlaylist(rootName, genreName, playlistName)
    return "SUCCESS: playlist ensured " & rootName & " / " & genreName & " / " & playlistName
end ensurePlaylist

on copyTrack(pathArgs)
    if (count of pathArgs) is not 4 then
        return "ERROR: copy_track requires track_id/root/genre/playlist path"
    end if

    set trackPID to item 1 of pathArgs
    set rootName to item 2 of pathArgs
    set genreName to item 3 of pathArgs
    set playlistName to item 4 of pathArgs

    tell application "Music"
        set sourceTrack to my sourceTrackByPersistentID(trackPID)
        if sourceTrack is missing value then
            return "ERROR: source track not found: " & trackPID
        end if

        set targetPlaylist to my ensureTargetPlaylist(rootName, genreName, playlistName)
        if my targetHasTrack(targetPlaylist, sourceTrack) then
            return "SUCCESS: track already exists in " & playlistName
        end if

        duplicate sourceTrack to targetPlaylist
        return "SUCCESS: track copied to " & playlistName
    end tell
end copyTrack

on ensureRootFolder(rootName)
    tell application "Music"
        set matches to every folder playlist whose name is rootName
        if (count of matches) > 1 then
            error "Ambiguous root folder " & rootName & ": multiple folder playlists share this name"
        end if
        if (count of matches) is 1 then
            repeat with candidate in matches
                return contents of candidate
            end repeat
        end if
        make new folder playlist with properties {name:rootName}
        set matches to every folder playlist whose name is rootName
        if (count of matches) is 0 then
            error "Could not create folder " & rootName
        end if
        if (count of matches) > 1 then
            error "Ambiguous root folder " & rootName & ": multiple folder playlists share this name"
        end if
        repeat with candidate in matches
            return contents of candidate
        end repeat
    end tell
end ensureRootFolder

on ensureGenreFolder(rootName, genreName)
    tell application "Music"
        set rootFolder to my ensureRootFolder(rootName)
        set genreFolder to my findUniqueFolderByNameAndParent(genreName, rootName)
        if genreFolder is not missing value then
            return genreFolder
        end if

        make new folder playlist at rootFolder with properties {name:genreName}
        set genreFolder to my findUniqueFolderByNameAndParent(genreName, rootName)
        if genreFolder is missing value then
            error "Could not create folder " & rootName & " / " & genreName
        end if
        return genreFolder
    end tell
end ensureGenreFolder

on ensureTargetPlaylist(rootName, genreName, playlistName)
    tell application "Music"
        set genreFolder to my ensureGenreFolder(rootName, genreName)
        set targetPlaylist to my findUniqueUserPlaylistByFullPath(playlistName, genreName, rootName)
        if targetPlaylist is not missing value then
            return targetPlaylist
        end if

        make new user playlist at genreFolder with properties {name:playlistName}
        set targetPlaylist to my findUniqueUserPlaylistByFullPath(playlistName, genreName, rootName)
        if targetPlaylist is missing value then
            error "Could not create playlist " & playlistName
        end if
        return targetPlaylist
    end tell
end ensureTargetPlaylist

on findUniqueFolderByNameAndParent(folderName, parentName)
    tell application "Music"
        set matches to every folder playlist whose name is folderName
        set foundFolder to missing value
        set foundCount to 0
        repeat with candidate in matches
            try
                if name of parent of candidate is parentName then
                    set foundFolder to contents of candidate
                    set foundCount to foundCount + 1
                end if
            end try
        end repeat
        if foundCount > 1 then
            error "Ambiguous folder path " & parentName & " / " & folderName
        end if
        if foundCount is 1 then
            return foundFolder
        end if
    end tell
    return missing value
end findUniqueFolderByNameAndParent

on findUniqueUserPlaylistByFullPath(playlistName, genreName, rootName)
    tell application "Music"
        set matches to every user playlist whose name is playlistName
        set foundPlaylist to missing value
        set foundCount to 0
        repeat with candidate in matches
            try
                if name of parent of candidate is genreName and name of parent of parent of candidate is rootName then
                    set foundPlaylist to contents of candidate
                    set foundCount to foundCount + 1
                end if
            end try
        end repeat
        if foundCount > 1 then
            error "Ambiguous playlist path " & rootName & " / " & genreName & " / " & playlistName
        end if
        if foundCount is 1 then
            return foundPlaylist
        end if
    end tell
    return missing value
end findUniqueUserPlaylistByFullPath

on sourceTrackByPersistentID(trackPID)
    tell application "Music"
        try
            set favouriteSongs to playlist "Favourite Songs"
            set favouriteMatches to every track of favouriteSongs whose persistent ID is trackPID
            if (count of favouriteMatches) > 0 then
                return item 1 of favouriteMatches
            end if
        end try

        try
            set libraryPlaylist to item 1 of library playlists
            set libraryMatches to every track of libraryPlaylist whose persistent ID is trackPID
            if (count of libraryMatches) > 0 then
                return item 1 of libraryMatches
            end if
        end try
    end tell
    return missing value
end sourceTrackByPersistentID

on targetHasTrack(targetPlaylist, sourceTrack)
    tell application "Music"
        set sourcePID to ""
        try
            set sourcePID to persistent ID of sourceTrack
        end try
        if sourcePID is not "" then
            try
                set pidMatches to every track of targetPlaylist whose persistent ID is sourcePID
                if (count of pidMatches) > 0 then
                    return true
                end if
            end try
        end if

        set sourceName to ""
        set sourceArtist to ""
        try
            set sourceName to name of sourceTrack
        end try
        try
            set sourceArtist to artist of sourceTrack
        end try

        repeat with existingTrack in tracks of targetPlaylist
            set existingName to ""
            set existingArtist to ""
            try
                set existingName to name of existingTrack
            end try
            try
                set existingArtist to artist of existingTrack
            end try
            if existingName is sourceName and existingArtist is sourceArtist then
                return true
            end if
        end repeat
    end tell
    return false
end targetHasTrack
