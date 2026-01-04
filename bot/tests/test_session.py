"""
Unit Test for bot/radio/session.py
"""
import sys
import unittest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from radio.session import RadioSession, SessionManager, get_session_manager
from radio.constants import (
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_PAUSED,
    SESSION_STATUS_STOPPED,
    STREAM_PORT_START
)

class TestRadioSession(unittest.TestCase):
    def test_session_expiry(self):
        """Test session expiration logic."""
        expires = datetime.now() - timedelta(minutes=1)
        session = RadioSession(
            id="test-id",
            user_id=123,
            stream_port=8000,
            stream_url="http://host:8000/",
            expires_at=expires
        )
        self.assertTrue(session.is_expired())
        self.assertEqual(session.get_remaining_seconds(), 0)

    def test_session_extension(self):
        """Test session extension capabilities."""
        session = RadioSession(
            id="test-id",
            user_id=123,
            stream_port=8000,
            stream_url="http://host:8000/",
            total_duration_played=1000
        )
        # MAX is 21600. 1000 + 20000 = 21000 (OK)
        self.assertTrue(session.can_extend(20000))
        # 1000 + 21000 = 22000 (Fail)
        self.assertFalse(session.can_extend(21000))

class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Reset SessionManager singleton and internal state for each test."""
        SessionManager._instance = None
        self.manager = get_session_manager()
        # Mock the _log_event to avoid DB issues
        self.manager._log_event = MagicMock(return_value=asyncio.Future())
        self.manager._log_event.return_value.set_result(None)

    async def test_singleton(self):
        """Verify SessionManager is a singleton."""
        self.assertEqual(self.manager, get_session_manager())

    async def test_create_session(self):
        """Test successful session creation."""
        session = await self.manager.create_session(user_id=1)
        self.assertIsNotNone(session)
        self.assertEqual(session.user_id, 1)
        self.assertEqual(session.stream_port, STREAM_PORT_START)
        self.assertEqual(session.status, SESSION_STATUS_ACTIVE)

    async def test_duplicate_session_prevention(self):
        """Verify user cannot have two active sessions."""
        await self.manager.create_session(user_id=1)
        second = await self.manager.create_session(user_id=1)
        self.assertIsNone(second)

    async def test_session_state_transitions(self):
        """Test pause, resume, and stop."""
        session = await self.manager.create_session(user_id=1)
        self.assertEqual(session.status, SESSION_STATUS_ACTIVE)
        
        # Pause
        success = await self.manager.pause_session(session.id)
        self.assertTrue(success)
        self.assertEqual(session.status, SESSION_STATUS_PAUSED)
        
        # Resume
        success = await self.manager.resume_session(session.id)
        self.assertTrue(success)
        self.assertEqual(session.status, SESSION_STATUS_ACTIVE)
        
        # Stop
        success = await self.manager.stop_session(session.id)
        self.assertTrue(success)
        self.assertEqual(session.status, SESSION_STATUS_STOPPED)

    async def test_port_allocation(self):
        """Test that ports are allocated correctly and reused."""
        s1 = await self.manager.create_session(user_id=1)
        s2 = await self.manager.create_session(user_id=2)
        
        self.assertEqual(s1.stream_port, STREAM_PORT_START)
        self.assertEqual(s2.stream_port, STREAM_PORT_START + 1)
        
        # Stop s1, its port should become available
        await self.manager.stop_session(s1.id)
        s3 = await self.manager.create_session(user_id=3)
        self.assertEqual(s3.stream_port, STREAM_PORT_START)

if __name__ == "__main__":
    unittest.main()
