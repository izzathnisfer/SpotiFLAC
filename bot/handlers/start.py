"""
Start and Help Command Handlers
"""

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand


WELCOME_TEXT = """
🎵 **Welcome to SpotiFLAC Bot!**

Download Spotify tracks as **lossless FLAC** from Tidal, Qobuz & Amazon Music.

━━━━━━━━━━━━━━━━━━━━━━

**🚀 Quick Start:**
Just paste a Spotify URL and I'll download it!

**🔍 Search:**
Use `/search <query>` to find music

**⚙️ Settings:**
Tap the button below or use /settings

━━━━━━━━━━━━━━━━━━━━━━

**Supported URLs:**
• 🎵 Track
• 💿 Album  
• 📋 Playlist
• 🎤 Artist

Send a link to get started! 🎧
"""


HELP_TEXT = """
📖 **SpotiFLAC Bot - Commands**

━━━ **Download** ━━━
• Paste any Spotify URL
• `/search <query>` - Search Spotify
• `/lyrics <url>` - Download .lrc lyrics
• `/cover <url>` - Download album art
• `/check <url>` - Check availability

━━━ **Queue** ━━━
• `/queue` - View download queue
• `/cancel` - Cancel downloads

━━━ **Settings** ━━━
• `/settings` - Open settings menu
  ├ Source: Auto/Tidal/Qobuz/Amazon
  ├ Quality: Lossless/Hi-Res
  └ Embed lyrics on/off

━━━ **Other** ━━━
• `/ping` - Check bot status
• `/help` - This message

━━━━━━━━━━━━━━━━━━━━━━

**💡 Tips:**
• Albums & playlists: select which tracks to download
• Files are cached - re-requests are instant!
• Supports up to 2GB FLAC files
"""


# Bot commands for Telegram menu
BOT_COMMANDS = [
    BotCommand("start", "🏠 Start the bot"),
    BotCommand("search", "🔍 Search Spotify"),
    BotCommand("settings", "⚙️ Bot settings"),
    BotCommand("queue", "📋 View download queue"),
    BotCommand("cancel", "❌ Cancel downloads"),
    BotCommand("lyrics", "🎤 Download lyrics"),
    BotCommand("cover", "🖼️ Download cover art"),
    BotCommand("check", "🔎 Check availability"),
    BotCommand("ping", "🏓 Check bot status"),
    BotCommand("help", "❓ Show help"),
]


async def setup_commands(client: Client):
    """Set bot commands in Telegram menu."""
    await client.set_bot_commands(BOT_COMMANDS)


async def handle(client: Client, message: Message):
    """Handle /start command."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=""),
            InlineKeyboardButton("⚙️ Settings", callback_data="set:menu"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="cmd:help")
        ]
    ])
    
    await message.reply(
        WELCOME_TEXT,
        reply_markup=keyboard
    )


async def handle_help(client: Client, message: Message):
    """Handle /help command."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="set:menu"),
        ]
    ])
    await message.reply(HELP_TEXT, reply_markup=keyboard)
