import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone, timedelta

# Suppress Python 3.12 deprecation: store datetime objects as ISO strings
sqlite3.register_adapter(datetime, lambda d: d.isoformat())

from .config import Config
from .logger import setup_logger

class CacheManager:
    """Manages SQLite database for tracks, playlists, and sync state."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or Config.SQLITE_DB_PATH)
        self.logger = setup_logger("cache_manager")
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Tracks table: Cache resolved Spotify IDs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    signature TEXT PRIMARY KEY,
                    track_id TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    last_updated TIMESTAMP
                )
            """)

            # Playlists table: Cache Spotify playlist metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    playlist_id TEXT PRIMARY KEY,
                    snapshot_id TEXT,
                    total_tracks INTEGER,
                    name TEXT,
                    last_updated TIMESTAMP
                )
            """)
            
            # Playlist Items table: Local state of Apple Music playlists for incremental diffing
            # Stores the expected Spotify track ID for items in an Apple playlist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS apple_playlist_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_name TEXT,
                    track_signature TEXT,
                    spotify_track_id TEXT,
                    position INTEGER,
                    UNIQUE(playlist_name, position)
                )
            """)
            
            # Apple Playlist Mapping table: Maps Apple Music playlist names to Spotify playlist IDs
            # This allows us to track playlists even when their names change
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS apple_playlist_mapping (
                    apple_playlist_name TEXT PRIMARY KEY,
                    spotify_playlist_id TEXT NOT NULL,
                    spotify_playlist_name TEXT,
                    last_synced TIMESTAMP,
                    created_at TIMESTAMP
                )
            """)
            
            # Index for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracks_signature ON tracks(signature)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_apple_playlist_name ON apple_playlist_state(playlist_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mapping_spotify_id ON apple_playlist_mapping(spotify_playlist_id)")

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def get_track(self, signature: str) -> Optional[str]:
        """Retrieve a cached track ID by its signature, respecting TTL if configured."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if Config.CACHE_TTL_DAYS and Config.CACHE_TTL_DAYS > 0:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=Config.CACHE_TTL_DAYS)
                    cursor.execute(
                        "SELECT track_id FROM tracks WHERE signature = ? AND last_updated >= ?",
                        (signature, cutoff.isoformat())
                    )
                else:
                    cursor.execute("SELECT track_id FROM tracks WHERE signature = ?", (signature,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.logger.error(f"Error reading track cache: {e}")
            return None

    def save_track(self, signature: str, track_id: Optional[str], title: str, artist: str, album: Optional[str]):
        """Cache a resolved track ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO tracks (signature, track_id, title, artist, album, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (signature, track_id, title, artist, album, datetime.now(timezone.utc)))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error saving track to cache: {e}")

    def get_playlist_metadata(self, playlist_id: str) -> Optional[Dict]:
        """Retrieve cached playlist metadata."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT snapshot_id, total_tracks, name, last_updated FROM playlists WHERE playlist_id = ?", (playlist_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "snapshot_id": row[0],
                        "total": row[1],
                        "name": row[2],
                        "last_updated": row[3]
                    }
                return None
        except Exception as e:
            self.logger.error(f"Error reading playlist cache: {e}")
            return None

    def save_playlist_metadata(self, playlist_id: str, snapshot_id: Optional[str], total: int, name: Optional[str] = None):
        """Cache playlist metadata. If name is None, the existing name is preserved."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if name is None:
                    # Preserve existing name
                    cursor.execute(
                        "SELECT name FROM playlists WHERE playlist_id = ?",
                        (playlist_id,)
                    )
                    row = cursor.fetchone()
                    name = row[0] if row else ""
                cursor.execute("""
                    INSERT OR REPLACE INTO playlists (playlist_id, snapshot_id, total_tracks, name, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (playlist_id, snapshot_id, total, name, datetime.now(timezone.utc)))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error saving playlist metadata: {e}")

    def get_apple_playlist_state(self, playlist_name: str) -> List[Dict]:
        """Get the last known state of an Apple Music playlist."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT track_signature, spotify_track_id, position 
                    FROM apple_playlist_state 
                    WHERE playlist_name = ? 
                    ORDER BY position ASC
                """, (playlist_name,))
                rows = cursor.fetchall()
                return [{"signature": r[0], "spotify_track_id": r[1], "position": r[2]} for r in rows]
        except Exception as e:
            self.logger.error(f"Error reading apple playlist state: {e}")
            return []

    def update_apple_playlist_state(self, playlist_name: str, tracks: List[Dict]):
        """
        Update the local state of an Apple Music playlist.
        tracks: List of dicts with keys 'signature' and 'spotify_track_id'
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Use a transaction to clear old state and insert new state
                cursor.execute("DELETE FROM apple_playlist_state WHERE playlist_name = ?", (playlist_name,))
                
                data_to_insert = [
                    (playlist_name, t["signature"], t["spotify_track_id"], i)
                    for i, t in enumerate(tracks)
                ]
                
                if data_to_insert:
                    cursor.executemany("""
                        INSERT INTO apple_playlist_state (playlist_name, track_signature, spotify_track_id, position)
                        VALUES (?, ?, ?, ?)
                    """, data_to_insert)
                
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating apple playlist state: {e}")

    def get_playlist_mapping(self, apple_playlist_name: str) -> Optional[str]:
        """Get the Spotify playlist ID for an Apple Music playlist name."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT spotify_playlist_id, spotify_playlist_name 
                    FROM apple_playlist_mapping 
                    WHERE apple_playlist_name = ?
                """, (apple_playlist_name,))
                row = cursor.fetchone()
                if row:
                    return row[0]  # Return spotify_playlist_id
                return None
        except Exception as e:
            self.logger.error(f"Error reading playlist mapping: {e}")
            return None

    def save_playlist_mapping(self, apple_playlist_name: str, spotify_playlist_id: str, spotify_playlist_name: str):
        """Save or update a playlist mapping."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Check if mapping exists
                cursor.execute("""
                    SELECT created_at FROM apple_playlist_mapping 
                    WHERE apple_playlist_name = ?
                """, (apple_playlist_name,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing mapping
                    cursor.execute("""
                        UPDATE apple_playlist_mapping 
                        SET spotify_playlist_id = ?, 
                            spotify_playlist_name = ?, 
                            last_synced = ?
                        WHERE apple_playlist_name = ?
                    """, (spotify_playlist_id, spotify_playlist_name, datetime.now(timezone.utc), apple_playlist_name))
                else:
                    # Insert new mapping
                    cursor.execute("""
                        INSERT INTO apple_playlist_mapping 
                        (apple_playlist_name, spotify_playlist_id, spotify_playlist_name, last_synced, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (apple_playlist_name, spotify_playlist_id, spotify_playlist_name, 
                          datetime.now(timezone.utc), datetime.now(timezone.utc)))
                
                conn.commit()
                self.logger.debug(f"Saved playlist mapping: {apple_playlist_name} -> {spotify_playlist_id}")
        except Exception as e:
            self.logger.error(f"Error saving playlist mapping: {e}")

    def get_all_playlist_mappings(self) -> List[Dict]:
        """Get all playlist mappings."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT apple_playlist_name, spotify_playlist_id, spotify_playlist_name, 
                           last_synced, created_at 
                    FROM apple_playlist_mapping 
                    ORDER BY last_synced DESC
                """)
                rows = cursor.fetchall()
                return [{
                    "apple_name": r[0],
                    "spotify_id": r[1],
                    "spotify_name": r[2],
                    "last_synced": r[3],
                    "created_at": r[4]
                } for r in rows]
        except Exception as e:
            self.logger.error(f"Error reading all playlist mappings: {e}")
            return []

    def delete_playlist_mapping(self, apple_playlist_name: str) -> bool:
        """Delete a playlist mapping."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM apple_playlist_mapping 
                    WHERE apple_playlist_name = ?
                """, (apple_playlist_name,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    self.logger.info(f"Deleted playlist mapping: {apple_playlist_name}")
                return deleted
        except Exception as e:
            self.logger.error(f"Error deleting playlist mapping: {e}")
            return False

    def clear_all_playlist_mappings(self) -> bool:
        """Clear all playlist mappings."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM apple_playlist_mapping")
                conn.commit()
                self.logger.info("Cleared all playlist mappings")
                return True
        except Exception as e:
            self.logger.error(f"Error clearing playlist mappings: {e}")
            return False

    def clear_tracks(self) -> bool:
        """Delete all rows from the tracks cache table."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM tracks")
                conn.commit()
            self.logger.info("Cleared all cached tracks")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing tracks cache: {e}")
            return False

    def clear_playlists(self) -> bool:
        """Delete all rows from the playlists metadata table."""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM playlists")
                conn.commit()
            self.logger.info("Cleared all cached playlist metadata")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing playlists cache: {e}")
            return False

    def clear_all(self) -> bool:
        """Clear both the track and playlist caches."""
        return self.clear_tracks() and self.clear_playlists()
