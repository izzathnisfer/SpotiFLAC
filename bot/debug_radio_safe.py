"""
Debug Radio Safe
Tests if the full radio import stack is now safe after refactoring asyncio.Lock/Event.
"""
import logging
import sys
import asyncio
from pyrogram import Client, idle
import config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="debug_radio.log",
    filemode="w"
)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logging.getLogger().addHandler(console)

logger = logging.getLogger(__name__)

logger.info("--- STARTING DEBUG RADIO SAFE ---")

try:
    logger.info("Importing handlers.radio...")
    from handlers import radio
    logger.info("Handlers imported.")
    
    app = Client(
        "debug_radio_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=str(config.DATA_DIR)
    )
    
    async def main():
        logger.info("Inside main(). Starting app...")
        await app.start()
        logger.info("App started! We are running.")
        logger.info("Idling...")
        await idle()
        logger.info("Idle finished. Stopping...")
        await app.stop()
        logger.info("App stopped.")

    logger.info("Calling app.run(main())")
    app.run(main()) 
    logger.info("--- EXITING SUCCESS ---")

except Exception as e:
    logger.error(f"--- FAILED ---: {e}", exc_info=True)
