"""
Radio Streaming Service - Main Entry Point (Phase 3)

Runs both FastAPI server and Telegram bot concurrently.
"""

import logging
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import config
from api.routes import router as api_router
from bot.client import get_bot, is_admin
from bot.handlers.start import start_command, help_command
from bot.handlers.radio import handle_radio_callback
from bot.handlers.admin import admin_command, handle_admin_callback
from bot.handlers.search import handle_spotify_link, handle_search_query, handle_search_callback, SPOTIFY_REGEX

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def setup_bot_handlers(bot: Client):
    """Register all bot handlers."""
    
    # Command handlers
    @bot.on_message(filters.command("start") & filters.private)
    async def on_start(client, message):
        await start_command(client, message)
    
    @bot.on_message(filters.command("help") & filters.private)
    async def on_help(client, message):
        await help_command(client, message)
    
    @bot.on_message(filters.command("admin") & filters.private)
    async def on_admin(client, message):
        await admin_command(client, message)
    
    # Spotify link handler
    @bot.on_message(filters.regex(SPOTIFY_REGEX) & filters.private)
    async def on_spotify_link(client, message):
        await handle_spotify_link(client, message)
    
    # Text message handler (for search)
    @bot.on_message(filters.text & filters.private & ~filters.command(["start", "help", "admin"]))
    async def on_text(client, message):
        await handle_search_query(client, message)
    
    # Callback query handlers
    @bot.on_callback_query(filters.regex(r"^radio:"))
    async def on_radio_callback(client, callback):
        await handle_radio_callback(client, callback)
    
    @bot.on_callback_query(filters.regex(r"^admin:"))
    async def on_admin_callback(client, callback):
        await handle_admin_callback(client, callback)
    
    @bot.on_callback_query(filters.regex(r"^search:"))
    async def on_search_callback(client, callback):
        await handle_search_callback(client, callback)
    
    @bot.on_callback_query(filters.regex(r"^queue:"))
    async def on_queue_callback(client, callback):
        # Handle queue callbacks (remove, clear)
        from bot.handlers.radio import handle_radio_callback
        await handle_radio_callback(client, callback)
    
    logger.info("Bot handlers registered")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - start/stop bot with server."""
    # Startup
    logger.info("=" * 50)
    logger.info("🎵 Radio Streaming Service Starting...")
    logger.info("=" * 50)
    
    # Start Telegram bot
    bot = get_bot()
    setup_bot_handlers(bot)
    
    try:
        await bot.start()
        me = await bot.get_me()
        logger.info(f"🤖 Bot started: @{me.username}")
        
        # Notify admins
        for admin_id in config.ADMIN_IDS:
            try:
                public_ip = config.get_public_ip()
                await bot.send_message(
                    admin_id,
                    f"📻 **Radio Service Started!**\n\n"
                    f"🔗 Server: `http://{public_ip}:{config.RADIO_PORT}`\n"
                    f"🤖 Bot: @{me.username}\n\n"
                    f"Use /start to begin!"
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        # Continue anyway, API will still work
    
    logger.info(f"📡 API server on port {config.RADIO_PORT}")
    logger.info("=" * 50)
    
    yield  # Server runs here
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Stop all active sessions
    from core.player import get_all_players
    for player in get_all_players():
        await player.stop()
    
    # Stop bot
    try:
        await bot.stop()
        logger.info("Bot stopped")
    except:
        pass
    
    logger.info("Goodbye!")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Validate configuration
    errors = config.validate_config()
    if errors:
        logger.warning("Configuration warnings:")
        for error in errors:
            logger.warning(f"  - {error}")
    
    app = FastAPI(
        title="Radio Streaming Service",
        description="Lightweight audio streaming server with Telegram control",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router)
    
    return app


app = create_app()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║           🎵 Radio Streaming Service 🎵              ║
    ║              Phase 3 - Telegram Bot                  ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.RADIO_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower()
    )
