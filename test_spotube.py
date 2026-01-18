import asyncio
import logging
from pathlib import Path
import sys
import os

sys.path.append(os.getcwd())

from radio.core.spotubedl_downloader import search_tracks

logging.basicConfig(level=logging.INFO)

async def main():
    print("Testing SpotubeDL Search Keys...")
    try:
        results = await search_tracks("Oorum Blood")
        if results:
            print(f"First Result Keys: {results[0].keys()}")
            print(f"First Result Data: {results[0]}")
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
