"""
Unit Test for bot/handlers/check.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import check, download

class TestCheckHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch backend
        self.patch_backend = patch('handlers.check.backend')
        self.mock_backend = self.patch_backend.start()
        self.mock_api = self.mock_backend.get_client.return_value
        
        # Clear sessions
        download._user_sessions.clear()

    async def asyncTearDown(self):
        self.patch_backend.stop()

    async def test_handle_invalid_url(self):
        """Test /check with invalid URL."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "/check invalid_url"
        
        await check.handle(client, message)
        
        message.reply.assert_called_with("❌ Please provide a Spotify track URL")

    async def test_handle_success(self):
        """Test successful availability check."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "/check https://open.spotify.com/track/123"
        
        # Mock metadata
        self.mock_api.get_metadata = AsyncMock(return_value={
            "track": {
                "name": "Test Track",
                "artists": "Test Artist",
                "spotify_id": "123",
                "isrc": "TEST1"
            }
        })
        
        # Mock availability
        self.mock_api.check_availability = AsyncMock(return_value={
            "tidal": True,
            "qobuz": False,
            "amazon": True,
            "tidal_url": "http://tidal.com"
        })
        
        await check.handle(client, message)
        
        message.reply.assert_called()
        status_msg = message.reply.return_value
        status_msg.edit_text.assert_called()
        text = status_msg.edit_text.call_args[0][0]
        
        self.assertIn("Test Track", text)
        self.assertIn("✅ Tidal", text)
        self.assertIn("❌ Qobuz", text)

    async def test_handle_callback(self):
        """Test check callback from menu."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "chk:123"
        callback.from_user.id = 999
        
        # Setup session
        download._user_sessions[999] = {
            "tracks": {
                "key": {"spotify_id": "123", "isrc": "TEST1", "name": "Session Track"}
            }
        }
        
        self.mock_api.check_availability = AsyncMock(return_value={"tidal": True})
        
        await check.handle_callback(client, callback)
        
        callback.message.reply.assert_called()
        text = callback.message.reply.call_args[0][0]
        self.assertIn("Session Track", text)
        self.assertIn("✅ Tidal", text)

if __name__ == "__main__":
    unittest.main()
