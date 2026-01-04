"""
Unit Test for bot/services/backend.py
"""
import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import backend

class TestBackendService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reset singleton
        backend._client = None
        self.client = backend.get_client()
        
        # Mock session
        self.mock_session = AsyncMock()
        self.mock_session.closed = False  # Critical: prevents creating real session
        self.client._session = self.mock_session
        
        # Mock request context manager
        self.mock_response = AsyncMock()
        self.mock_response.status = 200
        self.mock_response.json = AsyncMock(return_value={"success": True})
        self.mock_response.text = AsyncMock(return_value="OK")
        
        # Use MagicMock for get/post so they return the context manager immediately, not a coroutine
        self.mock_session.get = MagicMock()
        self.mock_session.get.return_value.__aenter__.return_value = self.mock_response
        
        self.mock_session.post = MagicMock()
        self.mock_session.post.return_value.__aenter__.return_value = self.mock_response

    async def test_get_metadata_success(self):
        """Test metadata fetch success."""
        self.mock_response.json.return_value = {"track": {"name": "Test"}}
        
        result = await self.client.get_metadata("http://spotify/track/1")
        
        self.assertEqual(result["track"]["name"], "Test")
        self.mock_session.get.assert_called()

    async def test_get_metadata_error(self):
        """Test metadata fetch error."""
        self.mock_response.status = 500
        self.mock_response.text.return_value = "Server Error"
        
        result = await self.client.get_metadata("http://spotify/track/1")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Server Error")

    async def test_download_track(self):
        """Test track download."""
        await self.client.download_track(
            isrc="TEST",
            spotify_id="123",
            track_name="Test",
            artist_name="Artist",
            album_name="Album"
        )
        
        self.mock_session.post.assert_called()
        url = self.mock_session.post.call_args[0][0]
        self.assertTrue(url.endswith("/download"))
        
        payload = self.mock_session.post.call_args[1]["json"]
        self.assertEqual(payload["isrc"], "TEST")

    async def test_check_availability(self):
        """Test availability check."""
        self.mock_response.json.return_value = {"tidal": True}
        
        result = await self.client.check_availability("123", "TEST")
        
        self.assertTrue(result["tidal"])
        self.mock_session.get.assert_called()
        url = self.mock_session.get.call_args[0][0]
        self.assertTrue(url.endswith("/check"))

    async def test_health_check(self):
        """Test health check."""
        result = await self.client.health_check()
        self.assertTrue(result)
        
        self.mock_response.status = 500
        result = await self.client.health_check()
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
