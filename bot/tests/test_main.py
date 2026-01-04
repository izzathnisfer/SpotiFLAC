"""
Unit Test for bot/main.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestMain(unittest.TestCase):
    @patch('pyrogram.Client.__init__', return_value=None)
    def test_bot_initialization(self, mock_init):
        """Verify SpotiFLACBot initializes with correct config."""
        from main import SpotiFLACBot
        import config
        
        bot = SpotiFLACBot()
        
        # Check if super().__init__ was called with expected arguments
        mock_init.assert_called_once()
        args, kwargs = mock_init.call_args
        self.assertEqual(kwargs['api_id'], config.API_ID)
        self.assertEqual(kwargs['api_hash'], config.API_HASH)
        self.assertEqual(kwargs['bot_token'], config.BOT_TOKEN)
        self.assertEqual(kwargs['plugins']['root'], "handlers")

    def test_get_loop_id(self):
        """Verify get_loop_id returns a value or 'no_loop'."""
        from main import get_loop_id
        result = get_loop_id()
        self.assertTrue(isinstance(result, (int, str)))

if __name__ == "__main__":
    unittest.main()
