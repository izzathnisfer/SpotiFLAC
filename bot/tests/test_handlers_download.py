"""
Unit Test for bot/handlers/download.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import download

class TestDownloadHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch backend
        self.patch_backend = patch('handlers.download.backend')
        self.mock_backend = self.patch_backend.start()
        self.mock_api = self.mock_backend.get_client.return_value
        
        # Patch database
        self.patch_db = patch('handlers.download.database')
        self.mock_db = self.patch_db.start()
        # Ensure db methods are async mocks
        self.mock_db.get_cached_file = AsyncMock(return_value=None)
        self.mock_db.get_user_settings = AsyncMock(return_value={})
        self.mock_db.cache_file = AsyncMock()
        
        # Patch config to avoid real path checks if any
        self.patch_config = patch('config.CACHE_CHANNEL_ID', -100123456)
        self.patch_config.start()
        
        # Patch os/path for file operations
        self.patch_path_exists = patch('pathlib.Path.exists', return_value=True)
        self.patch_path_exists.start()
        
        self.patch_os_remove = patch('os.remove')
        self.patch_os_remove.start()
        self.patch_stat = patch('pathlib.Path.stat')
        self.mock_stat = self.patch_stat.start()
        self.mock_stat.return_value.st_size = 1024

    async def asyncTearDown(self):
        self.patch_backend.stop()
        self.patch_db.stop()
        self.patch_config.stop()
        self.patch_path_exists.stop()
        self.patch_os_remove.stop()
        self.patch_stat.stop()

    async def test_handle_url_invalid(self):
        """Test URL handler with invalid URL."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "not a spotify url"
        
        await download.handle_url(client, message)
        
        message.reply.assert_called_with("❌ Invalid Spotify URL")

    async def test_handle_url_track(self):
        """Test handling a track URL."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "https://open.spotify.com/track/123"
        message.from_user.id = 123
        
        # Mock metadata response
        self.mock_api.get_metadata = AsyncMock(return_value={
            "track": {
                "name": "Test Track",
                "artists": "Test Artist",
                "isrc": "TEST123456",
                "duration_ms": 180000,
                "spotify_id": "123"
            }
        })
        
        await download.handle_url(client, message)
        
        # Check if status message was updated with track info
        status_msg = message.reply.return_value
        status_msg.edit_text.assert_called()
        args = status_msg.edit_text.call_args[0][0]
        self.assertIn("Test Track", args)
        self.assertIn("Test Artist", args)

    async def test_download_single_track_success(self):
        """Test successful single track download."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "dl:t:TEST123456"
        callback.from_user.id = 123
        callback.message.text = "Previous Display"
        
        # Mock session to return track
        with patch('handlers.download.get_track_from_session', new_callable=AsyncMock) as mock_get_track:
            mock_get_track.return_value = {
                "name": "Test Track",
                "isrc": "TEST123456",
                "duration_ms": 60000
            }
            
            # Mock download result
            self.mock_api.download_track = AsyncMock(return_value={
                "success": True,
                "file": "/tmp/test.flac"
            })
            
            # Mock client methods
            client.send_audio = AsyncMock()
            client.send_audio.return_value.id = 999
            client.send_audio.return_value.audio.file_id = "file_id_123"
            client.copy_message = AsyncMock()
            
            await download.download_single_track(client, callback, "TEST123456", 123)
            
            self.mock_api.download_track.assert_called_once()
            client.send_audio.assert_called_once()
            client.copy_message.assert_called_once()
            self.mock_db.cache_file.assert_called_once()

if __name__ == "__main__":
    unittest.main()
