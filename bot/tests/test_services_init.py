"""
Unit Test for bot/services/__init__.py
"""
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestServicesInit(unittest.TestCase):
    def test_exports(self):
        """Verify that service modules are exported."""
        try:
            from services import database, backend
        except ImportError as e:
            self.fail(f"Failed to import services: {e}")
            
        import services
        expected = ["database", "backend"]
        
        for module in expected:
            self.assertTrue(hasattr(services, module))
            self.assertIn(module, services.__all__)

if __name__ == "__main__":
    unittest.main()
