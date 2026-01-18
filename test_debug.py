import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from radio.core.spotubedl_downloader import search_tracks, get_download_link

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    print("--- Debugging SpotubeDL for 'kannukulla' ---")
    
    # 1. Search
    print("1. Searching...")
    try:
        results = await search_tracks("kannukulla")
        if not results:
            print("❌ No results found.")
            return
            
        first = results[0]
        print(f"✅ Found result: {first.get('name')} by {first.get('artist')}")
        sid = first.get("id")
        print(f"ID: {sid}")
        
        # 2. Get Link
        print("\n2. Getting download link...")
        link = await get_download_link(sid)
        
        if link:
            print(f"✅ Success! Link: {link[:50]}...")
        else:
            print("❌ Failed to get link. Check logs above.")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
