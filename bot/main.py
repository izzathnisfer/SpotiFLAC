"""
Minimal Subclass Test
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
        logger.info("SpotiFLACBot.start() called")
        await super().start()
        logger.info("SpotiFLACBot started successfully")
        
    async def stop(self, *args):
        logger.info("SpotiFLACBot.stop() called")
        await super().stop(*args)

app = SpotiFLACBot()

@app.on_message(filters.command("ping"))
async def handle_ping(client, message):
    logger.info("PING RECEIVED")
    await message.reply("SUBCLASS PONG")

if __name__ == "__main__":
    print("--- STARTING SUBCLASS BOT ---")
    app.run()
