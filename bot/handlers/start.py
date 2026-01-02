"""
Start and Help Command Handlers
"""

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


WELCOME_TEXT = """
🎵 **Welcome to SpotiFLAC Bot!**

Download Spotify tracks as **lossless FLAC** from Tidal, Qobuz & Amazon Music.

**How to use:**
Simply send a Spotify URL and I'll handle the rest!

**Supported URLs:**
• Track: `spotify.com/track/...`
• Album: `spotify.com/album/...`
• Playlist: `spotify.com/playlist/...`
• Artist: `spotify.com/artist/...`

**Commands:**
/help - Show all commands
/settings - Configure quality & source
/queue - View download queue

Just paste a Spotify link to get started! 🚀
"""


HELP_TEXT = """
📖 **SpotiFLAC Bot Commands**

**Download:**
• Send any Spotify URL to download
• /lyrics `<url>` - Download lyrics only
• /cover `<url>` - Download cover art
• /check `<url>` - Check platform availability

**Queue:**
• /queue - View download queue
• /cancel - Cancel current download

**Settings:**
• /settings - Configure bot settings
  - Source: Auto/Tidal/Qobuz/Amazon
  - Quality: Lossless/Hi-Res
  - Embed lyrics on/off

**Other:**
• /ping - Check if bot is alive
• /help - Show this message

**Tips:**
🔸 Albums & playlists show a track list to select from
🔸 Downloaded files are cached - re-requests are instant!
🔸 Hi-Res FLAC files can be up to 2GB
"""


async def handle(client: Client, message: Message):
    """Handle /start command."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="set:menu"),
            InlineKeyboardButton("❓ Help", callback_data="cmd:help")
        ]
    ])
    
    await message.reply(
        WELCOME_TEXT,
        reply_markup=keyboard
    )


async def handle_help(client: Client, message: Message):
    """Handle /help command."""
    await message.reply(HELP_TEXT)
