"""
Unit Test for bot/radio/__init__.py
"""
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestRadioInit(unittest.TestCase):
    def test_exports(self):
        """Verify that all core classes are exported in radio/__init__.py"""
        import radio
        from radio.session import RadioSession, SessionManager
        from radio.queue import QueueItem, QueueManager
        
        # Verify imports from base module
        self.assertEqual(radio.RadioSession, RadioSession)
        self.assertEqual(radio.SessionManager, SessionManager)
        self.assertEqual(radio.QueueItem, QueueItem)
        self.assertEqual(radio.QueueManager, QueueManager)
        
        # Check __all__
        expected_all = [
            'RadioSession',
            'SessionManager', 
            'QueueItem',
            'QueueManager',
            'StreamingServer',
            'AudioTranscoder',
            'RadioScheduler',
            'RadioEngine',
        ]
        for item in expected_all:
            self.assertTrue(hasattr(radio, item), f"radio module missing {item}")

if __name__ == "__main__":
    unittest.main()
