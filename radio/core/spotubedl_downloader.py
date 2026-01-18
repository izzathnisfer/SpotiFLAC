"""
SpotubeDL Downloader Module
Interact with SpotubeDL API to search and download tracks.
"""

import httpx
import base64
import logging
import asyncio
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://spotubedl.com/api"

async def search_tracks(query: str) -> List[Dict]:
    """Search for tracks on SpotubeDL."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_BASE}/info/search/{query}")
            if resp.status_code == 200:
                data = resp.json()
                if "results" in data:
                    return data["results"]
    except Exception as e:
        logger.error(f"SpotubeDL search error: {e}")
    return []

async def get_download_link(spotify_id: str) -> Optional[str]:
    """
    Get direct download link for a Spotify track.
    Flow:
    1. Get metadata -> extract YouTube ID
    2. Convert endpoint -> get base64 encoded URL
    3. Decode -> return direct URL
    """
    try:
        async with httpx.AsyncClient() as client:
            # 1. Get Metadata
            meta_resp = await client.get(f"{API_BASE}/metadata/{spotify_id}")
            if meta_resp.status_code != 200:
                return None
            
            meta = meta_resp.json()
            youtube_url = meta.get("youtube_url")
            if not youtube_url:
                return None
            
            # Extract YouTube ID
            # URL format: https://music.youtube.com/watch?v=ID
            # or https://www.youtube.com/watch?v=ID
            import re
            yt_id_match = re.search(r'v=([a-zA-Z0-9_-]+)', youtube_url)
            if not yt_id_match:
                return None
            youtube_id = yt_id_match.group(1)
            
            # 2. Convert (Request 320kbps MP3)
            convert_url = f"{API_BASE}/convert/320/{youtube_id}?format=mp3"
            convert_resp = await client.get(convert_url)
            
            if convert_resp.status_code != 200:
                return None
            
            convert_data = convert_resp.json()
            encoded_url = convert_data.get("url")
            
            if not encoded_url:
                return None
            
            # 3. Decode Base64
            direct_url = base64.b64decode(encoded_url).decode('utf-8')
            return direct_url
            
    except Exception as e:
        logger.error(f"SpotubeDL link fetch error: {e}")
        return None

async def download_track(
    query: str, 
    output_dir: Path,
    filename: str = None
) -> Optional[str]:
    """
    Full workflow: Search -> Get Link -> Download File
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Search
        results = await search_tracks(query)
        if not results:
            logger.warning(f"No results found for {query}")
            return None
            
        track = results[0] # Best match
        spotify_id = track.get("id")
        
        if not filename:
            # Create safe filename from result
            safe_title = re.sub(r'[<>:"/\\|?*]', '', track.get("name", "track"))
            safe_artist = re.sub(r'[<>:"/\\|?*]', '', track.get("artist", "artist"))
            filename = f"{safe_artist} - {safe_title}.mp3"
            
        output_path = output_dir / filename
        if output_path.exists():
            return str(output_path)
            
        # 2. Get Link
        download_url = await get_download_link(spotify_id)
        if not download_url:
            logger.error(f"Failed to generate download link for {query}")
            return None
            
        # 3. Download File
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream('GET', download_url) as resp:
                if resp.status_code != 200:
                    logger.error(f"Download request failed: {resp.status_code}")
                    return None
                    
                with open(output_path, 'wb') as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                        
        logger.info(f"Downloaded: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"SpotubeDL download process failed: {e}")
        return None
