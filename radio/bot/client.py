"""
Radio Bot - Pyrogram Client Setup
"""

import logging
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

import config

logger = logging.getLogger(__name__)

# Global bot client
_bot: Client = None


def get_bot() -> Client:
    """Get the global bot client instance."""
    global _bot
    if _bot is None:
        _bot = Client(
            name="radio_bot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workdir=str(config.BASE_DIR)
        )
    return _bot


def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    return user_id in config.ADMIN_IDS
