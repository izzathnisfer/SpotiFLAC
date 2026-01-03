import os
import sys
import logging
from pyrogram import Client, filters
from dotenv import load_dotenv

load_dotenv()

# Configure logging to stdout
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

app = Client(
    'spotiflac_aws',
    api_id=int(os.getenv('API_ID')),
    api_hash=os.getenv('API_HASH'),
    bot_token=os.getenv('BOT_TOKEN'),
    workdir='./data'
)

@app.on_message(filters.command("ping"))
async def handle_ping(client, message):
    print(f'RECEIVED PING FROM {message.from_user.id}')
    await message.reply(f'BASELINE PONG')

@app.on_message(filters.all)
async def handle_all(client, message):
    print(f'RECEIVED ALL: {message.text}')

print('Starting Baseline Bot...')
app.run()
