"""
Unit Test for bot/radio/constants.py
"""
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestConstants(unittest.TestCase):
    def test_session_limits(self):
        """Verify session limit constants."""
        from radio import constants
        self.assertEqual(constants.MAX_SESSION_DURATION, 21600)
        self.assertEqual(constants.DEFAULT_SESSION_DURATION, 1800)
        self.assertEqual(constants.WARNING_THRESHOLD, 18000)

    def test_bitrates(self):
        """Verify bitrate constants."""
        from radio import constants
        self.assertEqual(constants.DEFAULT_BITRATE, 128)
        self.assertEqual(constants.HIGH_BITRATE, 320)

    def test_ports(self):
        """Verify port range constants."""
        from radio import constants
        self.assertEqual(constants.STREAM_PORT_START, 8100)
        self.assertEqual(constants.STREAM_PORT_END, 8199)
        self.assertEqual(constants.STREAM_PORT_RANGE, (8100, 8199))

    def test_statuses(self):
        """Verify status constants."""
        from radio import constants
        self.assertEqual(constants.SESSION_STATUS_ACTIVE, "active")
        self.assertEqual(constants.QUEUE_STATUS_PENDING, "pending")
        self.assertEqual(constants.QUEUE_STATUS_PLAYING, "playing")

if __name__ == "__main__":
    unittest.main()
