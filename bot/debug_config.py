"""
Debug Config
Tests if config.py can be imported and values read without crashing or loop errors.
"""
import sys
import os

print("--- STARTING DEBUG CONFIG ---")
print(f"Python Version: {sys.version}")
print(f"CWD: {os.getcwd()}")

try:
    print("Importing config...")
    import config
    print("Config imported successfully.")
    
    print(f"API_ID: {config.API_ID} (Type: {type(config.API_ID)})")
    print(f"API_HASH: {config.API_HASH} (Type: {type(config.API_HASH)})")
    print(f"BOT_TOKEN: {config.BOT_TOKEN[:5]}... (Type: {type(config.BOT_TOKEN)})")
    print(f"DATABASE_PATH: {config.DATABASE_PATH} (Type: {type(config.DATABASE_PATH)})")
    print(f"RADIO_ENABLED: {config.RADIO_ENABLED} (Type: {type(config.RADIO_ENABLED)})")
    
    print("--- SUCCESS ---")
    
except Exception as e:
    print(f"--- FAILED ---")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
