"""
Unit Test for bot/handlers/__init__.py
"""
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestHandlersInit(unittest.TestCase):
    def test_exports(self):
        """Verify that all handler modules are exported."""
        try:
            from handlers import (
                start, download, settings, queue, 
                lyrics, cover, check, search
            )
        except ImportError as e:
            self.fail(f"Failed to import handlers: {e}")
            
        import handlers
        expected = [
            "start", "download", "settings", "queue", 
            "lyrics", "cover", "check", "search"
        ]
        
        for module in expected:
            self.assertTrue(hasattr(handlers, module))
            self.assertIn(module, handlers.__all__)

if __name__ == "__main__":
    unittest.main()
