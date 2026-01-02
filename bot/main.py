"""
SpotiFLAC Telegram Bot - Main Entry Point
"""

import logging
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

import config
from handlers import start, download, settings, queue, lyrics, cover, check, search
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


def create_app() -> Client:
    """Create and configure the Pyrogram client."""
    
    # Validate configuration
    errors = config.validate_config()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    # Create client with MTProto (2GB file support!)
    app = Client(
        name="spotiflac_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=str(config.DATA_DIR)
    )
    
    return app


# Create the app instance
app = create_app()


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
    """Handle /start command."""
    if not is_allowed(message.from_user.id):
        await message.reply("⛔ You are not authorized to use this bot.")
        return
    await start.handle(client, message)


@app.on_message(filters.command("help"))
async def handle_help(client: Client, message: Message):
    """Handle /help command."""
    if not is_allowed(message.from_user.id):
        return
    await start.handle_help(client, message)


@app.on_message(filters.command("settings"))
async def handle_settings(client: Client, message: Message):
    """Handle /settings command."""
    if not is_allowed(message.from_user.id):
        return
    await settings.handle(client, message)


@app.on_message(filters.command("queue"))
async def handle_queue(client: Client, message: Message):
    """Handle /queue command."""
    if not is_allowed(message.from_user.id):
        return
    await queue.handle(client, message)


@app.on_message(filters.command("cancel"))
async def handle_cancel(client: Client, message: Message):
    """Handle /cancel command."""
    if not is_allowed(message.from_user.id):
        return
    await queue.handle_cancel(client, message)


@app.on_message(filters.command("lyrics"))
async def handle_lyrics(client: Client, message: Message):
    """Handle /lyrics <url> command."""
    if not is_allowed(message.from_user.id):
        return
    await lyrics.handle(client, message)


@app.on_message(filters.command("cover"))
async def handle_cover(client: Client, message: Message):
    """Handle /cover <url> command."""
    if not is_allowed(message.from_user.id):
        return
    await cover.handle(client, message)


@app.on_message(filters.command("check"))
async def handle_check(client: Client, message: Message):
    """Handle /check <url> command."""
    if not is_allowed(message.from_user.id):
        return
    await check.handle(client, message)


@app.on_message(filters.command("search"))
async def handle_search(client: Client, message: Message):
    """Handle /search <query> command."""
    if not is_allowed(message.from_user.id):
        return
    await search.handle(client, message)


# =============================================================================
# URL Auto-Detection Handler
# =============================================================================

# Regex for Spotify URLs
SPOTIFY_URL_PATTERN = r"(https?://)?(open\.)?spotify\.com/(track|album|playlist|artist)/[a-zA-Z0-9]+"

@app.on_message(filters.regex(SPOTIFY_URL_PATTERN) & filters.private)
async def handle_spotify_url(client: Client, message: Message):
    """Handle Spotify URLs sent directly."""
    if not is_allowed(message.from_user.id):
        return
    await download.handle_url(client, message)


# =============================================================================
# Callback Query Handler
# =============================================================================

@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    """Handle all callback queries from inline keyboards."""
    if not is_allowed(callback_query.from_user.id):
        await callback_query.answer("⛔ Not authorized", show_alert=True)
        return
    
    data = callback_query.data
    
    # Route to appropriate handler based on prefix
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
    else:
        await callback_query.answer()


# =============================================================================
# Startup & Shutdown
# =============================================================================

@app.on_message(filters.command("ping") & filters.private)
async def handle_ping(client: Client, message: Message):
    """Simple health check."""
    await message.reply("🏓 Pong! Bot is running.")


async def startup():
    """Initialize on startup."""
    logger.info("Initializing database...")
    await init_database()
    logger.info("SpotiFLAC Bot started successfully!")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    print("""
    ╔═══════════════════════════════════════╗
    ║       SpotiFLAC Telegram Bot          ║
    ║   2GB uploads via Pyrogram MTProto    ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Run startup tasks
    loop = asyncio.new_event_loop()
    loop.run_until_complete(startup())
    
    # Start the bot
    logger.info("Starting bot...")
    app.run()
