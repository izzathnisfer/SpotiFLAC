"""
Unit Test for bot/radio/queue.py
"""
import sys
import unittest
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from radio.queue import QueueItem, QueueManager, get_queue_manager
from radio.constants import (
    QUEUE_STATUS_PENDING,
    QUEUE_STATUS_PLAYING,
    QUEUE_STATUS_PLAYED,
    MAX_SESSION_DURATION
)

class TestQueueItem(unittest.TestCase):
    def test_display_name(self):
        """Test the display_name formatting."""
        item = QueueItem(
            id=1, session_id="sid", position=1,
            track_isrc="ISRC1", track_name="Song", artist_name="Artist"
        )
        self.assertEqual(item.display_name(), "Artist - Song")

class TestQueueManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Reset QueueManager singleton and internal state for each test."""
        QueueManager._instance = None
        self.manager = get_queue_manager()

    async def test_singleton(self):
        """Verify QueueManager is a singleton."""
        self.assertEqual(self.manager, get_queue_manager())

    async def test_add_track(self):
        """Test adding track to queue."""
        item = await self.manager.add_track(
            session_id="s1", track_isrc="T1", 
            track_name="N1", artist_name="A1", duration=300
        )
        self.assertIsNotNone(item)
        self.assertEqual(item.position, 1)
        self.assertEqual(await self.manager.get_total_duration("s1"), 300)

    async def test_duration_limit(self):
        """Verify 6-hour limit enforcement."""
        # Add a very long track
        item = await self.manager.add_track(
            session_id="s1", track_isrc="T1", 
            track_name="N1", artist_name="A1", 
            duration=MAX_SESSION_DURATION + 1
        )
        self.assertIsNone(item)

    async def test_reorder_logic(self):
        """Test remove and move logic reorders correctly."""
        await self.manager.add_track("s1", "T1", "N1", "A1", 100)
        await self.manager.add_track("s1", "T2", "N2", "A2", 100)
        await self.manager.add_track("s1", "T3", "N3", "A3", 100)
        
        # Remove middle track
        await self.manager.remove_track("s1", 2)
        queue = await self.manager.get_queue("s1")
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0].position, 1)
        self.assertEqual(queue[1].position, 2)
        self.assertEqual(queue[1].track_name, "N3")

    async def test_status_updates(self):
        """Test marking tracks as playing/played."""
        await self.manager.add_track("s1", "T1", "N1", "A1", 100)
        await self.manager.add_track("s1", "T2", "N2", "A2", 100)
        
        # Mark 1 as playing
        await self.manager.mark_track_playing("s1", 1)
        q = await self.manager.get_queue("s1")
        self.assertEqual(q[0].status, QUEUE_STATUS_PLAYING)
        
        # Mark 2 as playing (1 should become PLAYED)
        await self.manager.mark_track_playing("s1", 2)
        q = await self.manager.get_queue("s1")
        self.assertEqual(q[0].status, QUEUE_STATUS_PLAYED)
        self.assertEqual(q[1].status, QUEUE_STATUS_PLAYING)

if __name__ == "__main__":
    unittest.main()
