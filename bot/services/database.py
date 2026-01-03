"""
Database Service - SQLite with file cache and user settings
"""

import aiosqlite
from pathlib import Path
from typing import Optional
import config

# Database path
DB_PATH = config.DATABASE_PATH


async def init_database():
    """Initialize database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # File cache table - stores Telegram file IDs for downloaded tracks
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isrc TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                file_name TEXT,
                file_size INTEGER,
                quality TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                source TEXT DEFAULT 'auto',
                tidal_quality TEXT DEFAULT 'LOSSLESS',
                qobuz_quality TEXT DEFAULT '6',
                embed_lyrics INTEGER DEFAULT 0,
                embed_max_cover INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster ISRC lookups
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_cache_isrc ON file_cache(isrc)
        """)
        
        await db.commit()
    
    # Initialize radio streaming tables
    await init_radio_tables()


async def init_radio_tables():
    """Initialize database tables for radio streaming feature."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Radio sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS radio_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                stream_port INTEGER NOT NULL,
                stream_url TEXT NOT NULL,
                bitrate INTEGER DEFAULT 128,
                status TEXT DEFAULT 'active',
                repeat_enabled INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP,
                current_track_index INTEGER DEFAULT 0,
                current_track_position REAL DEFAULT 0,
                total_duration_played REAL DEFAULT 0
            )
        """)
        
        # Radio queue table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS radio_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                track_isrc TEXT NOT NULL,
                track_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                album_name TEXT,
                duration INTEGER NOT NULL DEFAULT 0,
                file_path TEXT,
                status TEXT DEFAULT 'pending',
                spotify_id TEXT,
                cover_url TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES radio_sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Radio logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS radio_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES radio_sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Indexes for faster queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_radio_sessions_user ON radio_sessions(user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_radio_queue_session ON radio_queue(session_id, position)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_radio_logs_session ON radio_logs(session_id)
        """)
        
        await db.commit()


# =============================================================================
# File Cache Operations
# =============================================================================

async def get_cached_file(isrc: str) -> Optional[dict]:
    """Get cached file info by ISRC. Returns None if not cached."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM file_cache WHERE isrc = ?",
            (isrc,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def cache_file(
    isrc: str,
    file_id: str,
    message_id: int,
    file_name: str = None,
    file_size: int = None,
    quality: str = None,
    source: str = None
):
    """Cache a file's Telegram file_id for future instant access."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO file_cache 
            (isrc, file_id, message_id, file_name, file_size, quality, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (isrc, file_id, message_id, file_name, file_size, quality, source))
        await db.commit()


async def get_cache_stats() -> dict:
    """Get cache statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM file_cache")
        count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT SUM(file_size) FROM file_cache")
        total_size = (await cursor.fetchone())[0] or 0
        
        return {
            "total_files": count,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


# =============================================================================
# User Settings Operations
# =============================================================================

async def get_user_settings(user_id: int) -> dict:
    """Get user settings. Returns defaults if not set."""
    defaults = {
        "user_id": user_id,
        "source": "auto",
        "tidal_quality": "LOSSLESS",
        "qobuz_quality": "6",
        "embed_lyrics": 0,
        "embed_max_cover": 1
    }
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return defaults


async def update_user_setting(user_id: int, key: str, value) -> None:
    """Update a single user setting."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Ensure user exists
        await db.execute("""
            INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
        """, (user_id,))
        
        # Update the setting
        await db.execute(f"""
            UPDATE user_settings 
            SET {key} = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (value, user_id))
        
        await db.commit()


async def save_user_settings(user_id: int, settings: dict) -> None:
    """Save all user settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_settings 
            (user_id, source, tidal_quality, qobuz_quality, embed_lyrics, embed_max_cover)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            settings.get("source", "auto"),
            settings.get("tidal_quality", "LOSSLESS"),
            settings.get("qobuz_quality", "6"),
            settings.get("embed_lyrics", 0),
            settings.get("embed_max_cover", 1)
        ))
        await db.commit()
