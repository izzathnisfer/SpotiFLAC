"""
Unit Tests for SpotiFLAC Telegram Bot
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig:
    """Test configuration loading."""
    
    def test_config_loads(self):
        """Test that config module loads without error."""
        import config
        assert hasattr(config, 'API_ID')
        assert hasattr(config, 'API_HASH')
        assert hasattr(config, 'BOT_TOKEN')
        assert hasattr(config, 'CACHE_CHANNEL_ID')
    
    def test_validate_config_returns_errors(self):
        """Test that validate_config returns errors for missing values."""
        import config
        
        # Save originals
        orig_api_id = config.API_ID
        orig_api_hash = config.API_HASH
        
        # Set to invalid
        config.API_ID = 0
        config.API_HASH = ""
        
        errors = config.validate_config()
        assert len(errors) > 0
        assert any("API_ID" in e for e in errors)
        assert any("API_HASH" in e for e in errors)
        
        # Restore
        config.API_ID = orig_api_id
        config.API_HASH = orig_api_hash


class TestDatabase:
    """Test database operations."""
    
    @pytest.fixture
    async def db(self, tmp_path):
        """Create a temporary database."""
        import config
        from services import database
        
        # Override database path
        config.DATABASE_PATH = tmp_path / "test.db"
        
        await database.init_database()
        yield database
    
    @pytest.mark.asyncio
    async def test_init_database(self, db):
        """Test database initialization."""
        # Database should be created
        import config
        assert config.DATABASE_PATH.exists()
    
    @pytest.mark.asyncio
    async def test_cache_file_and_retrieve(self, db):
        """Test caching and retrieving a file."""
        isrc = "TEST123456789"
        file_id = "some_telegram_file_id"
        message_id = 12345
        
        await db.cache_file(
            isrc=isrc,
            file_id=file_id,
            message_id=message_id,
            file_name="test.flac",
            file_size=12345678,
            quality="LOSSLESS",
            source="tidal"
        )
        
        cached = await db.get_cached_file(isrc)
        assert cached is not None
        assert cached['file_id'] == file_id
        assert cached['message_id'] == message_id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_cache(self, db):
        """Test getting a non-cached file returns None."""
        cached = await db.get_cached_file("NONEXISTENT")
        assert cached is None
    
    @pytest.mark.asyncio
    async def test_user_settings_defaults(self, db):
        """Test user settings return defaults."""
        settings = await db.get_user_settings(999999)
        assert settings['source'] == 'auto'
        assert settings['tidal_quality'] == 'LOSSLESS'
    
    @pytest.mark.asyncio
    async def test_update_user_setting(self, db):
        """Test updating a single user setting."""
        user_id = 123456
        
        await db.update_user_setting(user_id, "source", "qobuz")
        
        settings = await db.get_user_settings(user_id)
        assert settings['source'] == 'qobuz'


class TestURLParsing:
    """Test Spotify URL parsing."""
    
    def test_parse_track_url(self):
        """Test parsing track URL."""
        from handlers.download import parse_spotify_url
        
        url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"
        url_type, spotify_id = parse_spotify_url(url)
        
        assert url_type == "track"
        assert spotify_id == "4iV5W9uYEdYUVa79Axb7Rh"
    
    def test_parse_album_url(self):
        """Test parsing album URL."""
        from handlers.download import parse_spotify_url
        
        url = "https://open.spotify.com/album/6PFPjumGRpZnBzqnDci6qJ"
        url_type, spotify_id = parse_spotify_url(url)
        
        assert url_type == "album"
        assert spotify_id == "6PFPjumGRpZnBzqnDci6qJ"
    
    def test_parse_playlist_url(self):
        """Test parsing playlist URL."""
        from handlers.download import parse_spotify_url
        
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        url_type, spotify_id = parse_spotify_url(url)
        
        assert url_type == "playlist"
        assert spotify_id == "37i9dQZF1DXcBWIGoYBM5M"
    
    def test_parse_invalid_url(self):
        """Test parsing invalid URL returns None."""
        from handlers.download import parse_spotify_url
        
        url = "https://example.com/not/spotify"
        url_type, spotify_id = parse_spotify_url(url)
        
        assert url_type is None
        assert spotify_id is None


class TestFormatters:
    """Test utility formatters."""
    
    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        from handlers.download import format_duration
        
        assert format_duration(30000) == "0:30"
        assert format_duration(90000) == "1:30"
    
    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        from handlers.download import format_duration
        
        assert format_duration(180000) == "3:00"
        assert format_duration(215000) == "3:35"
    
    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        from handlers.download import format_duration
        
        assert format_duration(3600000) == "1:00:00"
        assert format_duration(3661000) == "1:01:01"


class TestKeyboards:
    """Test keyboard generation."""
    
    def test_track_selection_keyboard(self):
        """Test track selection keyboard generation."""
        from handlers.download import create_track_selection_keyboard
        
        tracks = [
            {"isrc": "TEST1", "name": "Track 1"},
            {"isrc": "TEST2", "name": "Track 2"},
            {"isrc": "TEST3", "name": "Track 3"},
        ]
        selected = {"TEST2"}
        
        keyboard = create_track_selection_keyboard(tracks, selected, 0, 123, "album")
        
        # Should have buttons
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
