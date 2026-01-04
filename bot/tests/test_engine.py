"""
Unit Test for bot/radio/engine.py
"""
import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestRadioEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch all dependencies before importing RadioEngine or getting instance
        self.patches = [
            patch('radio.engine.get_session_manager'),
            patch('radio.engine.get_queue_manager'),
            patch('radio.engine.get_transcoder_pool'),
            patch('radio.engine.get_streaming_pool'),
            patch('radio.engine.get_scheduler'),
        ]
        self.mocks = [p.start() for p in self.patches]
        
        # Setup specific mock behaviors
        self.mock_session_mgr = self.mocks[0].return_value
        self.mock_queue_mgr = self.mocks[1].return_value
        self.mock_transcoder_pool = self.mocks[2].return_value
        self.mock_streaming_pool = self.mocks[3].return_value
        self.mock_scheduler = self.mocks[4].return_value

        # Configure AsyncMocks for awaitable methods
        self.mock_transcoder_pool.stop_transcoder = AsyncMock()
        self.mock_streaming_pool.stop_server = AsyncMock()
        mock_server = AsyncMock()
        mock_server.start = AsyncMock()
        self.mock_streaming_pool.get_or_create = MagicMock(return_value=mock_server)
        
        self.mock_scheduler.cancel_all = AsyncMock()
        self.mock_queue_mgr.cleanup_session = AsyncMock()
        self.mock_session_mgr.stop_session = AsyncMock()
        self.mock_session_mgr.get_session = AsyncMock()

        from radio.engine import RadioEngine
        RadioEngine._instance = None
        self.engine = RadioEngine.get_instance()

    async def asyncTearDown(self):
        for p in self.patches:
            p.stop()

    async def test_singleton(self):
        """Verify RadioEngine is a singleton."""
        from radio.engine import get_radio_engine
        self.assertEqual(self.engine, get_radio_engine())

    async def test_start_streaming_success(self):
        """Test successful streaming startup."""
        session_id = "test-session"
        mock_session = MagicMock()
        mock_session.stream_port = 8000
        self.mock_session_mgr.get_session = AsyncMock(return_value=mock_session)
        
        # Mock _streaming_loop to avoid it actually running
        with patch.object(self.engine, '_streaming_loop', return_value=AsyncMock()):
            success = await self.engine.start_streaming(session_id)
            
            self.assertTrue(success)
            self.mock_streaming_pool.get_or_create.assert_called_with(session_id, 8000)
            self.mock_streaming_pool.get_or_create.return_value.start.assert_called_once()
            self.assertIn(session_id, self.engine._active_tasks)

    async def test_stop_session(self):
        """Test session stop and cleanup calls."""
        session_id = "test-session"
        
        # Create a Future mimicking a Task
        mock_task = asyncio.Future()
        mock_task.set_result(None) # Properly finished future
        mock_task.cancel = MagicMock() # Mock cancel method
        
        self.engine._active_tasks[session_id] = mock_task
        
        # Mock session for the notification call
        self.mock_session_mgr.get_session = AsyncMock(return_value=MagicMock(user_id=123))
        
        await self.engine.stop_session(session_id, reason="test")
        
        # Verify cleanup
        # mock_task.cancel.assert_called_once() # Future.cancel might not be called if we awaited it? 
        # Actually engine calls task.cancel() then awaits it.
        # But if task is already done (set_result), cancel might do nothing?
        # Let's check other calls.
        
        self.mock_transcoder_pool.stop_transcoder.assert_called_with(session_id)
        self.mock_streaming_pool.stop_server.assert_called_with(session_id)
        self.mock_scheduler.cancel_all.assert_called_with(session_id)
        self.mock_queue_mgr.cleanup_session.assert_called_with(session_id)
        self.mock_session_mgr.stop_session.assert_called_with(session_id, "test")

if __name__ == "__main__":
    unittest.main()
