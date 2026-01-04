"""
Unit Test for bot/handlers/cover.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import cover, download

class TestCoverHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch backend
        self.patch_backend = patch('handlers.cover.backend')
        self.mock_backend = self.patch_backend.start()
        self.mock_api = self.mock_backend.get_client.return_value
        
        # Patch os/path
        self.patch_exists = patch('pathlib.Path.exists', return_value=True)
        self.patch_exists.start()
        self.patch_remove = patch('os.remove')
        self.patch_remove.start()
        
        download._user_sessions.clear()

    async def asyncTearDown(self):
        self.patch_backend.stop()
        self.patch_exists.stop()
        self.patch_remove.stop()

    async def test_handle_success(self):
        """Test successful cover download."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "/cover https://open.spotify.com/track/123"
        message.chat.id = 123
        
        # Mock metadata
        self.mock_api.get_metadata = AsyncMock(return_value={
            "track": {
                "name": "Test Track",
                "artists": "Test Artist",
                "images": "http://img.url"
            }
        })
        
        # Mock download
        self.mock_api.download_cover = AsyncMock(return_value={
            "success": True,
            "file": "/tmp/cover.jpg"
        })
        
        await cover.handle(client, message)
        
        self.mock_api.download_cover.assert_called()
        client.send_photo.assert_called_with(
            chat_id=123,
            photo="/tmp/cover.jpg",
            caption=unittest.mock.ANY
        )

    async def test_handle_callback(self):
        """Test cover callback."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "cov:123"
        callback.from_user.id = 999
        callback.message.chat.id = 999
        
        # Setup session
        download._user_sessions[999] = {
            "tracks": {
                "key": {"spotify_id": "123", "images": "http://img.url", "name": "Track"}
            }
        }
        
        self.mock_api.download_cover = AsyncMock(return_value={
            "success": True,
            "file": "/tmp/cover.jpg"
        })
        
        await cover.handle_callback(client, callback)
        
        client.send_photo.assert_called()

if __name__ == "__main__":
    unittest.main()
