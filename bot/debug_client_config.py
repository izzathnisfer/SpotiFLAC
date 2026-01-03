"""
Debug Client Config
Tests if Pyrogram Client can be initialized with config.py values.
"""
import sys
import os
import asyncio
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

print("--- STARTING DEBUG CLIENT CONFIG ---")
try:
    import config
    from pyrogram import Client
    
    print(f"API_ID: {config.API_ID}")
    
    print("Initializing Client...")
    app = Client(
        "debug_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir=str(config.DATA_DIR)
    )
    print("Client Initialized.")
    
    async def main():
        print("Inside main async.")
        print("Starting app...")
        await app.start()
        print("App started.")
        me = await app.get_me()
        print(f"Me: {me.first_name}")
        await app.stop()
        print("App stopped.")

    print("Running main...")
    app.run(main())
    print("--- SUCCESS ---")

except Exception as e:
    print(f"--- FAILED ---")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
