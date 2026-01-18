import asyncio
import logging
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from radio.core.spotubedl_downloader import download_track

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    print("Testing SpotubeDL download for 'Oorum Blood'...")
    try:
        path = await download_track("Oorum Blood", Path("radio/audio"), filename="test_spotube.mp3")
        if path:
            print(f"✅ Success! Downloaded to: {path}")
        else:
            print("❌ Failed to download.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
