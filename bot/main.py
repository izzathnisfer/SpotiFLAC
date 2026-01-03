"""
Minimal Main for Debugging
"""
import asyncio
import logging
import sys
from pyrogram import Client, filters, idle
from dotenv import load_dotenv

import config
from services.database import init_database

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Create app
app = Client(
    name="spotiflac_aws",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir=str(config.DATA_DIR)
)

@app.on_message(filters.command("ping"))
async def handle_ping(client, message):
    logger.info(f"PING RECEIVED from {message.from_user.id}")
    await message.reply("MINIMAL PONG")

async def main():
    logger.info("Initializing database...")
    await init_database()
    
    logger.info("Starting bot...")
    await app.start()
    logger.info("Bot started and listening...")
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
