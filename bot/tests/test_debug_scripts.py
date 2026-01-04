"""
Unit Test for Debug Scripts
"""
import sys
import unittest
import runpy
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestDebugScripts(unittest.TestCase):
    def test_debug_config(self):
        """Test debug_config.py execution."""
        script_path = str(Path(__file__).parent.parent / "debug_config.py")
        
        # We Mock print to suppress output
        with patch('builtins.print'):
            try:
                runpy.run_path(script_path, run_name="__main__")
            except Exception as e:
                self.fail(f"debug_config.py failed: {e}")

    # debug_client_config.py likely connects to Telegram or checks env vars
    # debug_radio_safe.py likely requires ffmpeg or similar
    
    # We can add them if needed, but debug_config is the main one listed first.
    # Let's add them wrapped in try/except or mocks if they do network calls.

if __name__ == "__main__":
    unittest.main()
