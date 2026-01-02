"""
Backend Service - HTTP client for Go backend API
"""

import aiohttp
import asyncio
import logging
from typing import Optional
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class BackendClient:
    """HTTP client for communicating with Go backend API."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.BACKEND_URL
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 min for large downloads
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # =========================================================================
    # Metadata Endpoints
    # =========================================================================
    
    async def get_metadata(self, spotify_url: str, timeout: int = 60) -> dict:
        """
        Fetch metadata for a Spotify URL.
        Returns track/album/playlist/artist info.
        """
        session = await self._get_session()
        params = {"url": spotify_url, "timeout": timeout}
        
        try:
            async with session.get(f"{self.base_url}/metadata", params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    logger.error(f"Metadata fetch failed: {error}")
                    return {"error": error}
        except asyncio.TimeoutError:
            return {"error": "Request timed out"}
        except Exception as e:
            logger.error(f"Backend error: {e}")
            return {"error": str(e)}
    
    async def search(self, query: str, limit: int = 10) -> dict:
        """Search Spotify for tracks/albums/artists."""
        session = await self._get_session()
        params = {"query": query, "limit": limit}
        
        try:
            async with session.get(f"{self.base_url}/search", params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": await resp.text()}
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================================
    # Download Endpoints
    # =========================================================================
    
    async def download_track(
        self,
        isrc: str,
        spotify_id: str,
        track_name: str,
        artist_name: str,
        album_name: str,
        album_artist: str = "",
        release_date: str = "",
        cover_url: str = "",
        track_number: int = 0,
        disc_number: int = 0,
        total_tracks: int = 0,
        source: str = "auto",
        quality: str = "",
        embed_lyrics: bool = False,
        embed_max_cover: bool = True,
        output_dir: str = None
    ) -> dict:
        """
        Download a track via the Go backend.
        Returns: {"success": bool, "file": str, "error": str}
        """
        session = await self._get_session()
        
        payload = {
            "isrc": isrc,
            "spotify_id": spotify_id,
            "track_name": track_name,
            "artist_name": artist_name,
            "album_name": album_name,
            "album_artist": album_artist,
            "release_date": release_date,
            "cover_url": cover_url,
            "track_number": track_number,
            "disc_number": disc_number,
            "total_tracks": total_tracks,
            "source": source,
            "quality": quality,
            "embed_lyrics": embed_lyrics,
            "embed_max_cover": embed_max_cover,
            "output_dir": output_dir or str(config.DOWNLOAD_PATH)
        }
        
        try:
            async with session.post(f"{self.base_url}/download", json=payload) as resp:
                return await resp.json()
        except asyncio.TimeoutError:
            return {"success": False, "error": "Download timed out"}
        except Exception as e:
            logger.error(f"Download error: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # Lyrics & Cover
    # =========================================================================
    
    async def download_lyrics(
        self,
        spotify_id: str,
        track_name: str,
        artist_name: str,
        output_dir: str = None
    ) -> dict:
        """Download lyrics for a track."""
        session = await self._get_session()
        
        payload = {
            "spotify_id": spotify_id,
            "track_name": track_name,
            "artist_name": artist_name,
            "output_dir": output_dir or str(config.DOWNLOAD_PATH)
        }
        
        try:
            async with session.post(f"{self.base_url}/lyrics", json=payload) as resp:
                return await resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def download_cover(
        self,
        cover_url: str,
        track_name: str,
        artist_name: str,
        output_dir: str = None
    ) -> dict:
        """Download cover art."""
        session = await self._get_session()
        
        payload = {
            "cover_url": cover_url,
            "track_name": track_name,
            "artist_name": artist_name,
            "output_dir": output_dir or str(config.DOWNLOAD_PATH)
        }
        
        try:
            async with session.post(f"{self.base_url}/cover", json=payload) as resp:
                return await resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # Platform Availability
    # =========================================================================
    
    async def check_availability(self, spotify_id: str, isrc: str) -> dict:
        """Check track availability on Tidal/Qobuz/Amazon."""
        session = await self._get_session()
        params = {"spotify_id": spotify_id, "isrc": isrc}
        
        try:
            async with session.get(f"{self.base_url}/check", params=params) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================================
    # Analysis
    # =========================================================================
    
    async def analyze_file(self, file_path: str) -> dict:
        """Analyze audio quality of a file."""
        session = await self._get_session()
        params = {"file": file_path}
        
        try:
            async with session.get(f"{self.base_url}/analyze", params=params) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> bool:
        """Check if backend is reachable."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except:
            return False


# Global client instance
_client: Optional[BackendClient] = None


def get_client() -> BackendClient:
    """Get the global backend client instance."""
    global _client
    if _client is None:
        _client = BackendClient()
    return _client
