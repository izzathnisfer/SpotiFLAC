"""
Unit Test for bot/services/database.py
"""
import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import database

class TestDatabaseService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Use in-memory database for testing
        self.patch_path = patch('config.DATABASE_PATH', ":memory:")
        self.patch_path.start()
        
        # We need to mock path.parent.mkdir because :memory: has no parent
        self.patch_mkdir = patch('pathlib.Path.mkdir')
        self.patch_mkdir.start()
        
        # Re-initialize database for each test
        await database.init_database()

    async def asyncTearDown(self):
        self.patch_path.stop()
        self.patch_mkdir.stop()

    async def test_user_settings(self):
        """Test user settings CRUD."""
        user_id = 123
        
        # Get defaults
        settings = await database.get_user_settings(user_id)
        self.assertEqual(settings['source'], 'auto')
        
        # Update setting
        await database.update_user_setting(user_id, 'source', 'tidal')
        settings = await database.get_user_settings(user_id)
        self.assertEqual(settings['source'], 'tidal')
        
        # Save multiple settings
        new_settings = {"source": "qobuz", "tidal_quality": "HI_RES"}
        await database.save_user_settings(user_id, new_settings)
        settings = await database.get_user_settings(user_id)
        self.assertEqual(settings['source'], 'qobuz')
        self.assertEqual(settings['tidal_quality'], 'HI_RES')

    async def test_file_cache(self):
        """Test file cache operations."""
        isrc = "TEST12345"
        await database.cache_file(
            isrc=isrc,
            file_id="file_id_1",
            message_id=100,
            file_name="test.flac",
            file_size=1024
        )
        
        cached = await database.get_cached_file(isrc)
        self.assertIsNotNone(cached)
        self.assertEqual(cached['file_id'], "file_id_1")
        
        # Test missing file
        cached = await database.get_cached_file("MISSING")
        self.assertIsNone(cached)

    async def test_radio_logs(self):
        """Test radio logging."""
        session_id = "sess1"
        # We need to create a session because of foreign key constraint?
        # The schema uses FOREIGN KEY (session_id) REFERENCES radio_sessions(id) ON DELETE CASCADE
        # So we must insert a session first.
        
        await database.save_radio_session({
            "id": session_id,
            "user_id": 1,
            "stream_port": 8000,
            "stream_url": "http://url",
            "expires_at": "2025-01-01 00:00:00"
        })
        
        await database.log_radio_event(session_id, "test_event", {"data": 123})
        
        logs = await database.get_radio_logs(session_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['event_type'], "test_event")

if __name__ == "__main__":
    unittest.main()
