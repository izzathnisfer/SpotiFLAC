"""
Unit Test for bot/handlers/search.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import search

class TestSearchHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch backend service
        self.patch_backend = patch('services.backend.get_client')
        self.mock_get_client = self.patch_backend.start()
        self.mock_api = self.mock_get_client.return_value
        
        # Patch download handler (since it's imported locally in callbacks)
        self.patch_download = patch('handlers.download.handle_url', new_callable=AsyncMock)
        self.mock_handle_url = self.patch_download.start()
        
        # We need to install the patch on sys.modules or mock the import in search.py
        # But since the import happens inside the function, we can just patch it 
        # using patch.dict on sys.modules if needed, OR mock the target function 
        # if it's imported at module level.
        # In this case: `from handlers import download` inside `handle_callback`.
        # Patching `handlers.download.handle_url` SHOULD work if `handlers.download` is already imported or will be.
        
    async def asyncTearDown(self):
        self.patch_backend.stop()
        self.patch_download.stop()

    async def test_handle_search_missing_query(self):
        """Test /search without query."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "/search"
        
        await search.handle(client, message)
        
        message.reply.assert_called()
        self.assertIn("Usage:", message.reply.call_args[0][0])

    async def test_handle_search_success(self):
        """Test successful search."""
        client = AsyncMock()
        message = AsyncMock()
        message.text = "/search daft punk"
        
        # Mock API response
        self.mock_api.search = AsyncMock(return_value={
            "tracks": [{"name": "Track 1", "artists": "Artist 1", "id": "t1"}],
            "albums": [{"name": "Album 1", "artists": "Artist 1", "id": "a1"}],
            "artists": [{"name": "Artist 1", "id": "r1"}]
        })
        
        await search.handle(client, message)
        
        self.mock_get_client.assert_called()
        self.mock_api.search.assert_called_with("daft punk", limit=10)
        # Verify status message was edited with results
        # reply returns a status_msg mock, we check edit_text on that
        status_msg = message.reply.return_value
        status_msg.edit_text.assert_called()
        args = status_msg.edit_text.call_args[0][0]
        self.assertIn("Track 1", args)

    async def test_handle_callback_track(self):
        """Test selecting a track from search results."""
        client = AsyncMock()
        callback = AsyncMock()
        callback.data = "src:t:123"
        callback.from_user = MagicMock()
        callback.message.reply = AsyncMock()
        
        # We need to ensure the local import inside search.py picks up our mock
        # Since we patched 'handlers.download.handle_url', and search.py does 'from handlers import download'
        # This relies on 'handlers' package being importable and containing 'download'
        
        await search.handle_callback(client, callback)
        
        self.mock_handle_url.assert_called_once()
        args = self.mock_handle_url.call_args[0]
        self.assertIn("https://open.spotify.com/track/123", args[1].text)

if __name__ == "__main__":
    unittest.main()
