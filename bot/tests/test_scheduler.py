"""
Unit Test for bot/radio/scheduler.py
"""
import sys
import unittest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from radio.scheduler import RadioScheduler, get_scheduler

class TestRadioScheduler(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        RadioScheduler._instance = None
        self.scheduler = get_scheduler()
        self.mock_client = AsyncMock()
        self.scheduler.set_bot_client(self.mock_client)

    async def test_singleton(self):
        self.assertEqual(self.scheduler, get_scheduler())

    async def test_schedule_expiration_immediate(self):
        """Test expiration when time has already passed."""
        past_time = datetime.now() - timedelta(seconds=10)
        
        # Callback mock
        callback = AsyncMock()
        self.scheduler.set_expire_callback(callback)
        
        await self.scheduler.schedule_expiration("s1", 123, past_time)
        
        # Should call immediately
        callback.assert_called_with("s1")
        self.mock_client.send_message.assert_called()

    async def test_schedule_future_task(self):
        """Test task creation for future event."""
        future_time = datetime.now() + timedelta(seconds=100)
        
        with patch('asyncio.create_task') as mock_create_task:
            await self.scheduler.schedule_expiration("s1", 123, future_time)
            mock_create_task.assert_called_once()
            self.assertIn("expiration", self.scheduler._tasks["s1"])

    async def test_cancel_all(self):
        """Verify cancellation of all tasks for a session."""
        mock_task = MagicMock(spec=asyncio.Task)
        mock_task.done.return_value = False
        
        self.scheduler._tasks["s1"] = {"expiration": mock_task}
        await self.scheduler.cancel_all("s1")
        
        mock_task.cancel.assert_called_once()
        self.assertNotIn("s1", self.scheduler._tasks)

if __name__ == "__main__":
    unittest.main()
