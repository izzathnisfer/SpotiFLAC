import asyncio
import logging
import sys
import os
from pathlib import Path

sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'radio'))

from radio.core.ytdlp_downloader import download_from_youtube
import config

logging.basicConfig(level=logging.INFO)

async def main():
    query = "Sai Abhyankkar - Kannukulla"
    print(f"--- Debugging SoundCloud Fallback for '{query}' ---")
    
    try:
        output_dir = Path("debug_audio")
        output_dir.mkdir(exist_ok=True)
        
        # Force scsearch1
        path = await download_from_youtube(
            query=query,
            output_dir=output_dir,
            audio_format="mp3",
            audio_quality="192"
        )
        
        if path:
            print(f"✅ Downloaded to: {path}")
            size = path.stat().st_size
            print(f"Size: {size} bytes ({size/1024/1024:.2f} MB)")
        else:
            print("❌ Download returned None")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
