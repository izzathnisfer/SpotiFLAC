"""
Unit Test for bot/handlers/radio.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import radio

class TestRadioHandler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch all singleton getters
        self.patches = [
            patch('handlers.radio.get_session_manager'),
            patch('handlers.radio.get_queue_manager'),
            patch('handlers.radio.get_scheduler'),
            patch('handlers.radio.get_streaming_pool'),
            patch('handlers.radio.get_transcoder_pool'),
        ]
        self.mocks = [p.start() for p in self.patches]
        
        self.mock_session_mgr = self.mocks[0].return_value
        self.mock_queue_mgr = self.mocks[1].return_value
        self.mock_scheduler = self.mocks[2].return_value
        self.mock_streaming_pool = self.mocks[3].return_value
        self.mock_transcoder_pool = self.mocks[4].return_value
        
        # Ensure async methods are awaitable
        self.mock_session_mgr.create_session = AsyncMock()
        self.mock_session_mgr.get_user_session = AsyncMock()
        self.mock_session_mgr.stop_session = AsyncMock()
        self.mock_session_mgr.pause_session = AsyncMock()
        self.mock_session_mgr.resume_session = AsyncMock()
        self.mock_session_mgr.toggle_repeat = AsyncMock()
        
        self.mock_queue_mgr.get_queue = AsyncMock()
        self.mock_queue_mgr.get_total_duration = AsyncMock()
        self.mock_queue_mgr.get_queue_length = AsyncMock()
        self.mock_queue_mgr.get_current_track = AsyncMock()
        self.mock_queue_mgr.cleanup_session = AsyncMock()
        self.mock_queue_mgr.shuffle_queue = AsyncMock()
        
        self.mock_scheduler.schedule_expiration = AsyncMock()
        self.mock_scheduler.notify_session_started = AsyncMock()
        self.mock_scheduler.cancel_all = AsyncMock()
        
        self.mock_streaming_pool.stop_server = AsyncMock()
        self.mock_transcoder_pool.stop_transcoder = AsyncMock()

    async def asyncTearDown(self):
        for p in self.patches:
            p.stop()

    async def test_handle_radio_no_session(self):
        """Test /radio when no session exists."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        self.mock_session_mgr.get_user_session = AsyncMock(return_value=None)
        
        await radio.handle_radio(client, message)
        
        message.reply.assert_called_once()
        self.assertIn("No Active Radio Session", message.reply.call_args[0][0])

    async def test_handle_radio_start_success(self):
        """Test happy path for /radio_start."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        self.mock_session_mgr.get_user_session = AsyncMock(return_value=None) # No existing session
        
        # Mock session creation
        mock_session = MagicMock()
        mock_session.id = "sess1"
        mock_session.stream_url = "http://test.url"
        self.mock_session_mgr.create_session = AsyncMock(return_value=mock_session)
        
        await radio.handle_radio_start(client, message)
        
        self.mock_session_mgr.create_session.assert_called_with(123)
        self.mock_scheduler.notify_session_started.assert_called_once()

    async def test_handle_radio_end(self):
        """Test /radio_end."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        
        mock_session = MagicMock()
        mock_session.id = "sess1"
        self.mock_session_mgr.get_user_session = AsyncMock(return_value=mock_session)
        
        await radio.handle_radio_end(client, message)
        
        self.mock_streaming_pool.stop_server.assert_called_with("sess1")
        self.mock_transcoder_pool.stop_transcoder.assert_called_with("sess1")
        self.mock_session_mgr.stop_session.assert_called_with("sess1", "user_request")

if __name__ == "__main__":
    unittest.main()
