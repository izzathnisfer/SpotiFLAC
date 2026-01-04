"""
Unit Test for bot/config.py
"""
import sys
import os
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestConfig(unittest.TestCase):
    def test_paths_defined(self):
        """Verify that essential paths are defined as Path objects."""
        import config
        self.assertIsInstance(config.BASE_DIR, Path)
        self.assertIsInstance(config.DATA_DIR, Path)
        self.assertIsInstance(config.DOWNLOAD_PATH, Path)
        self.assertIsInstance(config.DATABASE_PATH, Path)
    
    def test_radio_config_defaults(self):
        """Verify radio config defaults."""
        import config
        # Check types
        self.assertIsInstance(config.RADIO_ENABLED, bool)
        self.assertIsInstance(config.RADIO_HOST, str)
        self.assertIsInstance(config.RADIO_PUBLIC_HOST, str)

    def test_validation_function(self):
        """Verify validate_config returns errors if essential vars are missing."""
        import config
        # Save original values
        orig_api_id = config.API_ID
        
        # Test with missing API_ID
        config.API_ID = 0
        errors = config.validate_config()
        self.assertTrue(any("API_ID" in e for e in errors))
        
        # Restore
        config.API_ID = orig_api_id

if __name__ == "__main__":
    unittest.main()
