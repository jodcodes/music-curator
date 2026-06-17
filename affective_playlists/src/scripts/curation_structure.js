#!/usr/bin/env osascript -l JavaScript

const Music = Application("Music");
Music.includeStandardAdditions = true;

function firstNamed(collection, name) {
  const matches = collection.whose({ name });
  return matches.length > 0 ? matches[0] : null;
}

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function trackKey(artist, name) {
  return `${normalize(artist)}|||${normalize(name)}`;
}

function propertyValue(item, propertyName) {
  try {
    return item[propertyName]();
  } catch (e) {
    return "";
  }
}

function persistentID(item) {
  return String(propertyValue(item, "persistentID") || "");
}

function displayName(item) {
  return String(propertyValue(item, "name") || "");
}

function artistName(item) {
  return String(propertyValue(item, "artist") || "");
}

function ensureRootFolder(rootName) {
  let rootFolder = firstNamed(Music.folderPlaylists, rootName);
  if (rootFolder) {
    return rootFolder;
  }

  Music.folderPlaylists.push(Music.FolderPlaylist({ name: rootName }));
  rootFolder = firstNamed(Music.folderPlaylists, rootName);
  if (!rootFolder) {
    throw new Error(`Could not create folder ${rootName}`);
  }
  return rootFolder;
}

function ensureGenreFolder(rootName, genreName) {
  const rootFolder = ensureRootFolder(rootName);
  let genreFolder = firstNamed(rootFolder.folderPlaylists, genreName);
  if (genreFolder) {
    return genreFolder;
  }

  rootFolder.folderPlaylists.push(Music.FolderPlaylist({ name: genreName }));
  genreFolder = firstNamed(rootFolder.folderPlaylists, genreName);
  if (!genreFolder) {
    throw new Error(`Could not create folder ${rootName} / ${genreName}`);
  }
  return genreFolder;
}

function ensureTargetPlaylist(rootName, genreName, playlistName) {
  const genreFolder = ensureGenreFolder(rootName, genreName);
  let playlist = firstNamed(genreFolder.userPlaylists, playlistName);
  if (playlist) {
    return playlist;
  }

  genreFolder.userPlaylists.push(Music.UserPlaylist({ name: playlistName }));
  playlist = firstNamed(genreFolder.userPlaylists, playlistName);
  if (!playlist) {
    throw new Error(`Could not create playlist ${playlistName}`);
  }
  return playlist;
}

function sourceTrackByPersistentID(trackPID) {
  const favouriteSongs = firstNamed(Music.playlists, "Favourite Songs");
  if (favouriteSongs) {
    const favouriteMatches = favouriteSongs.tracks.whose({ persistentID: trackPID });
    if (favouriteMatches.length > 0) {
      return favouriteMatches[0];
    }
  }

  const libraryPlaylist = Music.libraryPlaylists[0];
  if (!libraryPlaylist) {
    throw new Error("main library playlist not found");
  }

  const matches = libraryPlaylist.tracks.whose({ persistentID: trackPID });
  return matches.length > 0 ? matches[0] : null;
}

function targetHasTrack(targetPlaylist, sourceTrack) {
  const sourcePersistentID = persistentID(sourceTrack);
  const sourceTrackKey = trackKey(artistName(sourceTrack), displayName(sourceTrack));
  const tracks = targetPlaylist.tracks;

  for (let i = 0; i < tracks.length; i += 1) {
    const existingTrack = tracks[i];
    if (sourcePersistentID && persistentID(existingTrack) === sourcePersistentID) {
      return true;
    }
    if (trackKey(artistName(existingTrack), displayName(existingTrack)) === sourceTrackKey) {
      return true;
    }
  }
  return false;
}

function ensureFolder(path) {
  if (path.length === 1) {
    ensureRootFolder(path[0]);
    return `SUCCESS: folder ensured ${path[0]}`;
  }
  if (path.length === 2) {
    ensureGenreFolder(path[0], path[1]);
    return `SUCCESS: folder ensured ${path[0]} / ${path[1]}`;
  }
  return "ERROR: ensure_folder requires root or root/genre path";
}

function ensurePlaylist(path) {
  if (path.length !== 3) {
    return "ERROR: ensure_playlist requires root/genre/playlist path";
  }
  ensureTargetPlaylist(path[0], path[1], path[2]);
  return `SUCCESS: playlist ensured ${path[0]} / ${path[1]} / ${path[2]}`;
}

function copyTrack(path) {
  if (path.length !== 4) {
    return "ERROR: copy_track requires track_id/root/genre/playlist path";
  }

  const sourcePersistentID = path[0];
  const sourceTrack = sourceTrackByPersistentID(sourcePersistentID);
  if (!sourceTrack) {
    return `ERROR: source track not found: ${sourcePersistentID}`;
  }

  const targetPlaylist = ensureTargetPlaylist(path[1], path[2], path[3]);
  if (targetHasTrack(targetPlaylist, sourceTrack)) {
    return `SUCCESS: track already exists in ${path[3]}`;
  }

  Music.duplicate(sourceTrack, { to: targetPlaylist });
  return `SUCCESS: track copied to ${path[3]}`;
}

function run(argv) {
  try {
    if (argv.length < 2) {
      return "ERROR: action and path required";
    }

    const action = argv[0];
    const path = argv.slice(1);
    if (action === "ensure_folder") {
      return ensureFolder(path);
    }
    if (action === "ensure_playlist") {
      return ensurePlaylist(path);
    }
    if (action === "copy_track") {
      return copyTrack(path);
    }
    return `ERROR: unsupported action: ${action}`;
  } catch (e) {
    return `ERROR: ${e.message || e}`;
  }
}
