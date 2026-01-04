"""
Unit Test for bot/radio/streaming.py
"""
import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from radio.streaming import RingBuffer, StreamingServerPool, get_streaming_pool

class TestRingBuffer(unittest.IsolatedAsyncioTestCase):
    async def test_write_read(self):
        """Test basic write and read from RingBuffer."""
        buffer = RingBuffer(max_size=65536)
        data = b"testdata"
        await buffer.write(data)
        
        # Read should return data
        result = await buffer.read()
        self.assertEqual(result, data)
        self.assertEqual(buffer.size, 0)

    async def test_read_timeout(self):
        """Verify read returns None on timeout if no data."""
        buffer = RingBuffer(max_size=65536)
        result = await buffer.read(timeout=0.01)
        self.assertIsNone(result)

    async def test_event_trigger(self):
        """Verify write triggers the new_data event."""
        buffer = RingBuffer(max_size=65536)
        
        async def delayed_write():
            await asyncio.sleep(0.05)
            await buffer.write(b"delayed")
            
        task = asyncio.create_task(delayed_write())
        
        # This read should wait until delayed_write completes
        result = await buffer.read(timeout=0.2)
        self.assertEqual(result, b"delayed")
        await task

class TestStreamingPool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        StreamingServerPool._instance = None
        self.pool = get_streaming_pool()

    async def test_singleton(self):
        """Verify StreamingServerPool is a singleton."""
        self.assertEqual(self.pool, get_streaming_pool())

    async def test_get_or_create(self):
        """Verify pool manages server instances."""
        server = self.pool.get_or_create("s1", 8001)
        self.assertEqual(server.port, 8001)
        self.assertEqual(self.pool.get("s1"), server)
        
        # Stop and remove
        with patch('radio.streaming.StreamingServer.stop', return_value=AsyncMock()) as mock_stop:
            await self.pool.stop_server("s1")
            self.assertIsNone(self.pool.get("s1"))

if __name__ == "__main__":
    unittest.main()
