"""
Unit Test for bot/handlers/queue.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import queue

class TestQueueHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Clear queue before each test
        queue._download_queues.clear()

    async def test_handle_empty_queue(self):
        """Test /queue with empty queue."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        
        await queue.handle(client, message)
        
        message.reply.assert_called_with("📭 Download queue is empty")

    async def test_handle_queue_with_items(self):
        """Test /queue with items."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        
        # Add mock item
        queue.add_to_queue(123, {"name": "Test Track", "status": "pending"})
        
        await queue.handle(client, message)
        
        message.reply.assert_called()
        args = message.reply.call_args[0][0]
        self.assertIn("Test Track", args)
        self.assertIn("⏳", args)

    async def test_handle_cancel(self):
        """Test /cancel command."""
        client = AsyncMock()
        message = AsyncMock()
        message.from_user.id = 123
        
        queue.add_to_queue(123, {"name": "Test Track"})
        
        await queue.handle_cancel(client, message)
        
        self.assertEqual(len(queue._download_queues[123]), 0)
        message.reply.assert_called()
        self.assertIn("Cancelled 1 items", message.reply.call_args[0][0])

    def test_queue_operations(self):
        """Test add, update, remove operations."""
        user_id = 999
        item = {"isrc": "TEST1", "name": "Test", "status": "pending"}
        
        queue.add_to_queue(user_id, item)
        self.assertEqual(len(queue._download_queues[user_id]), 1)
        
        queue.update_queue_status(user_id, "TEST1", "completed")
        self.assertEqual(queue._download_queues[user_id][0]["status"], "completed")
        
        queue.clear_completed(user_id)
        self.assertEqual(len(queue._download_queues[user_id]), 0)

if __name__ == "__main__":
    unittest.main()
