"""
Test Bot with Config
"""
import logging
import sys
from pyrogram import Client, filters
import config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Client(
    name="test_config_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir=str(config.DATA_DIR)
)

@app.on_message(filters.command("ping"))
async def handle_ping(client, message):
    logger.info("PING RECEIVED")
    await message.reply("CONFIG PONG")

if __name__ == "__main__":
    print("--- STARTING CONFIG BOT ---")
    app.run()
