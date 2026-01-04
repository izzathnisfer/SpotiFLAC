"""
Unit Test for bot/handlers/start.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers import start

class TestStartHandler(unittest.IsolatedAsyncioTestCase):
    async def test_setup_commands(self):
        """Verify command registration."""
        client = AsyncMock()
        await start.setup_commands(client)
        client.set_bot_commands.assert_called_once()
        args = client.set_bot_commands.call_args[0][0]
        self.assertEqual(len(args), len(start.BOT_COMMANDS))

    def test_setup_handlers(self):
        """Verify handler registration."""
        client = MagicMock()
        start.setup_handlers(client)
        self.assertEqual(client.add_handler.call_count, 2)

    async def test_handle_start(self):
        """Verify /start command handler."""
        client = AsyncMock()
        message = AsyncMock()
        
        await start.handle(client, message)
        
        message.reply.assert_called_once()
        args, kwargs = message.reply.call_args
        self.assertIn("Welcome", args[0])
        self.assertIsNotNone(kwargs.get('reply_markup'))

    async def test_handle_help(self):
        """Verify /help command handler."""
        client = AsyncMock()
        message = AsyncMock()
        
        await start.handle_help(client, message)
        
        message.reply.assert_called_once()
        args, kwargs = message.reply.call_args
        self.assertIn("Commands", args[0])
        self.assertIsNotNone(kwargs.get('reply_markup'))

    async def test_error_handling(self):
        """Verify error handling in handlers."""
        client = AsyncMock()
        message = AsyncMock()
        message.reply.side_effect = Exception("Test Error")
        
        # Should not raise exception, but log it and reply with error message
        # Note: We need to mock the logger to verify it logged, 
        # or check the second reply call which sends the error message.
        # But here message.reply raises the exception on the *first* call.
        # The handler catches it and calls reply *again* with error text.
        
        # We need check if reply is called twice? 
        # Actually since side_effect raises on every call, the second call also fails.
        # So we should scope the side effect.
        
        message.reply.side_effect = [Exception("Test Error"), AsyncMock()]
        
        await start.handle(client, message)
        self.assertEqual(message.reply.call_count, 2)

if __name__ == "__main__":
    unittest.main()
