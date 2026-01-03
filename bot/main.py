"""
SpotiFLAC Telegram Bot
Main entry point.
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from pyrogram import Client, idle
from pyrogram.enums import ParseMode

import config
from handlers import start, radio
from services.database import init_database
from radio.engine import get_radio_engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Debug trace function
def get_loop_id():
    try:
        return id(asyncio.get_running_loop())
    except RuntimeError:
        return "no_loop" 

# Reduce noise from libraries
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

class SpotiFLACBot(Client):
    def __init__(self):
        super().__init__(
            name="spotiflac_aws",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            workdir=str(config.DATA_DIR),
            plugins=dict(root="handlers")
        )

    async def start(self):
        logger.info(f"Starting SpotiFLAC Bot on loop {get_loop_id()}...")
        try:
            await super().start()
            logger.info("Pyrogram Client started.")
        except Exception as e:
            logger.critical(f"Pyrogram start failed: {e}", exc_info=True)
            raise e
        
        # Initialize database
        logger.info("Initializing database...")
        try:
            await init_database()
        except Exception as e:
            logger.error(f"Failed to init database: {e}", exc_info=True)
            # We continue anyway, though some features might fail
            
        # Register commands
        logger.info("Registering commands...")
        await start.setup_commands(self)
        
        # Register handlers
        logger.info("Registering handlers...")
        start.setup_handlers(self)
        radio.setup_handlers(self)
        
        # Initialize Radio Engine (starts streaming loop if active sessions exist)
        if config.RADIO_ENABLED:
            logger.info(f"Initializing Radio Engine on loop {get_loop_id()}...")
            # We don't need to explicitly start it here, just accessing it initializes the singleton
            try:
                engine = get_radio_engine()
                logger.info(f"Radio Engine initialized: {engine}")
            except Exception as e:
                logger.error(f"Failed to initialize Radio Engine: {e}", exc_info=True)
            
        me = await self.get_me()
        logger.info(f"Bot started as @{me.username} ({me.id})")
        
        # Notify admin of startup
        for user_id in config.ALLOWED_USERS:
            try:
                await self.send_message(user_id, "🚀 **SpotiFLAC Bot Started!**")
            except Exception:
                pass

    async def stop(self, *args):
        logger.info("Stopping SpotiFLAC Bot...")
        
        # Shutdown Radio Engine
        if config.RADIO_ENABLED:
            logger.info("Shutting down Radio Engine...")
            engine = get_radio_engine()
            await engine.shutdown_all()
            
        await super().stop()
        logger.info("Bot stopped.")

async def main():
    # Ensure data directory exists
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    app = SpotiFLACBot()
    
    # CRITICAL: Register handlers BEFORE starting the client
    # Pyrogram's dispatcher only picks up handlers registered before start()
    logger.info("Registering handlers BEFORE start...")
    start.setup_handlers(app)
    radio.setup_handlers(app)
    logger.info(f"Handlers registered: {len(app.dispatcher.groups)} groups")
    
    # Start the bot
    await app.start()
    
    # Idle until signal
    await idle()
    
    # Stop
    await app.stop()

if __name__ == "__main__":
    try:
        # Use asyncio.run for the main loop
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
