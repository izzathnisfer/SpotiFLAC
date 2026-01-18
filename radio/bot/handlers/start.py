"""
Radio Bot - Start Handler

Handles /start command and main menu display.
"""

import logging
from pyrogram import Client, filters
from pyrogram.types import Message

from bot.keyboards import main_menu_keyboard
from bot.client import is_admin
from core.player import get_player
import config

logger = logging.getLogger(__name__)


async def start_command(client: Client, message: Message):
    """Handle /start command."""
    user = message.from_user
    user_id = user.id
    username = user.username or user.first_name
    
    logger.info(f"/start from {username} ({user_id})")
    
    # Check if user has an active session
    player = get_player(str(user_id))
    has_session = player is not None
    
    welcome_text = """
🎵 **Welcome to Z Stream Radio!**

Your personal streaming station.
Stream music to VLC from anywhere.

"""
    
    if has_session:
        stream_url = config.get_stream_url(str(user_id))
        welcome_text += f"""
✅ **Your Radio is LIVE!**

🔗 **Stream URL:**
`{stream_url}`

Open VLC → Media → Open Network Stream
Paste the URL and hit Play!
"""
    else:
        welcome_text += """
Click **📻 Start Radio** to begin streaming.
"""
    
    if is_admin(user_id):
        welcome_text += "\n\n🔑 _You are an admin. Use /admin for dashboard._"
    
    await message.reply(
        welcome_text,
        reply_markup=main_menu_keyboard(has_session),
        quote=True
    )


async def help_command(client: Client, message: Message):
    """Handle /help command."""
    help_text = """
🎵 **Z Stream Radio - Help**

**How it works:**
1. Start your radio session
2. Copy the stream URL
3. Open VLC and paste the URL
4. Add songs via Spotify links or search

**Commands:**
• `/start` - Main menu
• `/admin` - Admin dashboard (admins only)

**Adding Songs:**
• Send a Spotify track/album/playlist link
• Or use the Search button

**Tips:**
• Multiple people can listen to your stream
• Add songs to keep the music playing!
"""
    
    await message.reply(help_text, quote=True)


def register_start_handlers(app: Client):
    """Register start-related handlers."""
    app.add_handler(
        filters.command("start") & filters.private,
        start_command
    )
    app.add_handler(
        filters.command("help") & filters.private,
        help_command
    )
