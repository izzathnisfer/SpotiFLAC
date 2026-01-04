"""
Unit Test for bot/handlers/settings.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import settings

class TestSettingsHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch database
        self.patch_db = patch('handlers.settings.database')
        self.mock_db = self.patch_db.start()
        
        self.mock_db.get_user_settings = AsyncMock(return_value={
            "source": "auto",
            "tidal_quality": "LOSSLESS",
            "embed_lyrics": 0,
            "embed_max_cover": 1
        })
        self.mock_db.update_user_setting = AsyncMock()

    async def asyncTearDown(self):
        self.patch_db.stop()

    async def test_handle_settings(self):
        """Test /settings command."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        
        await settings.handle(client, message)
        
        self.mock_db.get_user_settings.assert_called_with(123)
        message.reply.assert_called()
        self.assertIn("Your Settings", message.reply.call_args[0][0])

    async def test_callback_source_change(self):
        """Test changing source via callback."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "set:source:tidal"
        callback.from_user.id = 123
        callback.message.edit_text = AsyncMock()
        
        await settings.handle_callback(client, callback)
        
        self.mock_db.update_user_setting.assert_called_with(123, "source", "tidal")
        callback.message.edit_text.assert_called()

    async def test_callback_toggle_lyrics(self):
        """Test toggling lyrics."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "set:lyrics"
        callback.from_user.id = 123
        
        await settings.handle_callback(client, callback)
        
        # New value should be 1 (toggled from 0)
        self.mock_db.update_user_setting.assert_called_with(123, "embed_lyrics", 1)

if __name__ == "__main__":
    unittest.main()
