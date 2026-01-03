"""
SpotiFLAC Telegram Bot - Main Entry Point
Subclass Pattern with Radio Disabled
"""

import logging
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

import config
from handlers import start, download, settings, queue, lyrics, cover, check, search #, radio
from services.database import init_database

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Bot Client Subclass
# =============================================================================

class SpotiFLACBot(Client):
    def __init__(self):
        super().__init__(
            name="spotiflac_aws",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workdir=str(config.DATA_DIR)
        )
        
    async def start(self):
        # Start the client first (creates the loop and connection)
        await super().start()
        
        # Initialize database (on the same loop!)
        logger.info("Initializing database...")
        # await init_database()
        
        logger.info("SpotiFLAC Bot started successfully!")
        
    # async def stop(self, *args):
    #     # Graceful shutdown logic
    #     # try:
    #     #     from radio.engine import get_radio_engine
    #     #     engine = get_radio_engine()
    #     #     await engine.shutdown_all()
    #     #     logger.info("All radio sessions shut down gracefully")
    #     # except Exception as e:
    #     #     logger.error(f"Error shutting down radio sessions: {e}")
            
    #     await super().stop(*args)


# Create the app instance
app = SpotiFLACBot()


# =============================================================================
# Debug Middleware
# =============================================================================

@app.on_message(group=-1)
async def log_messages(client: Client, message: Message):
    """Log every incoming message for debugging."""
    text = message.text or "NoText"
    logger.info(f"DEBUG: Received message: {text}")


# =============================================================================
# Access Control Middleware
# =============================================================================

def is_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    if not config.ALLOWED_USERS:
        return True  # No restrictions
    return user_id in config.ALLOWED_USERS


# =============================================================================
# Command Handlers
# =============================================================================

@app.on_message(filters.command("start"))
async def handle_start(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await start.handle(client, message)


@app.on_message(filters.command("help"))
async def handle_help(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await start.handle_help(client, message)


@app.on_message(filters.command("settings"))
async def handle_settings(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await settings.handle(client, message)


@app.on_message(filters.command("queue"))
async def handle_queue(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await queue.handle(client, message)


@app.on_message(filters.command("cancel"))
async def handle_cancel(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await queue.handle_cancel(client, message)


@app.on_message(filters.command("lyrics"))
async def handle_lyrics(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await lyrics.handle(client, message)


@app.on_message(filters.command("cover"))
async def handle_cover(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await cover.handle(client, message)


@app.on_message(filters.command("check"))
async def handle_check(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await check.handle(client, message)


@app.on_message(filters.command("search"))
async def handle_search(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await search.handle(client, message)


# @app.on_message(filters.command("radio"))
# async def handle_radio(client: Client, message: Message):
#     if not is_allowed(message.from_user.id): return
#     await radio.handle_radio(client, message)


# @app.on_message(filters.command("radio_start"))
# async def handle_radio_start(client: Client, message: Message):
#     if not is_allowed(message.from_user.id): return
#     await radio.handle_radio_start(client, message)


# @app.on_message(filters.command("radio_end"))
# async def handle_radio_end(client: Client, message: Message):
#     if not is_allowed(message.from_user.id): return
#     await radio.handle_radio_end(client, message)


# =============================================================================
# URL Auto-Detection Handler
# =============================================================================

# Regex for Spotify URLs
SPOTIFY_URL_PATTERN = r"(https?://)?(open\.)?spotify\.com/(track|album|playlist|artist)/[a-zA-Z0-9]+"

@app.on_message(filters.regex(SPOTIFY_URL_PATTERN) & filters.private)
async def handle_spotify_url(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    await download.handle_url(client, message)


# =============================================================================
# Plain Text = Search
# =============================================================================

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help", "settings", "queue", "cancel", "lyrics", "cover", "check", "search", "ping", "radio", "radio_start", "radio_end"]))
async def handle_plain_text(client: Client, message: Message):
    if not is_allowed(message.from_user.id): return
    text = message.text.strip()
    if "spotify.com" in text.lower() or len(text) < 2: return
    message.text = f"/search {text}"
    await search.handle(client, message)


# =============================================================================
# Callback Query Handler
# =============================================================================

@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    if not is_allowed(callback_query.from_user.id):
        await callback_query.answer("⛔ Not authorized", show_alert=True)
        return
    
    data = callback_query.data
    
    if data.startswith("dl:"):
        await download.handle_callback(client, callback_query)
    elif data.startswith("set:"):
        await settings.handle_callback(client, callback_query)
    elif data.startswith("sel:") or data.startswith("page:"):
        await download.handle_selection_callback(client, callback_query)
    elif data.startswith("lyr:"):
        await lyrics.handle_callback(client, callback_query)
    elif data.startswith("cov:"):
        await cover.handle_callback(client, callback_query)
    elif data.startswith("chk:"):
        await check.handle_callback(client, callback_query)
    elif data.startswith("src:"):
        await search.handle_callback(client, callback_query)
    # elif data.startswith("rad:"):
    #     await radio.handle_callback(client, callback_query)
    else:
        await callback_query.answer()


# =============================================================================
# Health Check
# =============================================================================

@app.on_message(filters.command("ping") & filters.private)
async def handle_ping(client: Client, message: Message):
    """Simple health check."""
    await message.reply("🏓 Pong! Bot is running.")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════╗
    ║       SpotiFLAC Telegram Bot          ║
    ║   2GB uploads via Pyrogram MTProto    ║
    ║        + Radio Streaming 📻           ║
    ╚═══════════════════════════════════════╝
    """)
    app.run()
