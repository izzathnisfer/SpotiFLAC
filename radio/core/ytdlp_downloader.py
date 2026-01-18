"""
Radio Service - YT-DLP Downloader

Downloads audio from YouTube as a fallback when SpotiFLAC fails.
Uses yt-dlp Python module directly (not subprocess).
"""

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import config

logger = logging.getLogger(__name__)

# Thread pool for running yt-dlp synchronously
_executor = ThreadPoolExecutor(max_workers=3)

# YouTube cookies file path for bypassing bot detection
COOKIES_FILE = config.BASE_DIR / "assets" / "www.youtube.com_cookies.txt"


def _get_cookies_path() -> str | None:
    """Get cookies file path if it exists."""
    if COOKIES_FILE.exists():
        return str(COOKIES_FILE)
    return None


def _get_ytdlp():
    """Import and return yt_dlp module."""
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        logger.error("yt-dlp module not installed!")
        return None


def is_ytdlp_available() -> bool:
    """Check if yt-dlp is available."""
    return _get_ytdlp() is not None


def _search_youtube_sync(query: str, max_results: int = 5) -> list[dict]:
    """Synchronous YouTube search using yt-dlp module."""
    yt_dlp = _get_ytdlp()
    if not yt_dlp:
        return []
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_generic_extractor': False,
    }
    
    # Add cookies if available
    cookies_path = _get_cookies_path()
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            
            if not result or 'entries' not in result:
                return []
            
            results = []
            for entry in result['entries'][:max_results]:
                if entry:
                    results.append({
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Unknown"),
                        "channel": entry.get("channel", entry.get("uploader", "Unknown")),
                        "duration": entry.get("duration", 0),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                        "source": "youtube"
                    })
            return results
            
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []


async def search_youtube(query: str, max_results: int = 5) -> list[dict]:
    """
    Search YouTube for tracks.
    Returns list of results with title, channel, duration, url.
    """
    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _search_youtube_sync, query, max_results),
            timeout=30
        )
        return results
    except asyncio.TimeoutError:
        logger.warning("YouTube search timed out")
        return []
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []


def _download_youtube_sync(query: str, output_dir: Path, audio_format: str, audio_quality: str) -> Optional[str]:
    """Synchronous YouTube download using yt-dlp module."""
    yt_dlp = _get_ytdlp()
    if not yt_dlp:
        return None
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean query for filename
    safe_query = re.sub(r'[<>:"/\\|?*]', '', query)[:80]
    output_template = str(output_dir / f"{safe_query}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': audio_quality,
        }],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    # Add cookies if available
    cookies_path = _get_cookies_path()
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    
    logger.info(f"Downloading from YouTube: {query}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch1:{query}", download=True)
            
            if result and 'entries' in result and result['entries']:
                entry = result['entries'][0]
                # Find the downloaded file
                for ext in [audio_format, 'mp3', 'm4a', 'opus', 'webm']:
                    potential_file = output_dir / f"{safe_query}.{ext}"
                    if potential_file.exists():
                        logger.info(f"Downloaded: {potential_file}")
                        return str(potential_file)
            
            # Try to find any file matching pattern
            for f in output_dir.glob(f"{safe_query}*"):
                if f.suffix.lower() in ['.mp3', '.m4a', '.opus', '.webm', '.flac']:
                    return str(f)
            
            logger.warning("Downloaded file not found")
            return None
            
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None


async def download_from_youtube(
    query: str,
    output_dir: Path = None,
    audio_format: str = "mp3",
    audio_quality: str = "128"
) -> Optional[Path]:
    """
    Download audio from YouTube by searching for the query.
    Returns path to downloaded file or None on failure.
    """
    if output_dir is None:
        output_dir = config.AUDIO_DIR
    
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                _executor, 
                _download_youtube_sync, 
                query, output_dir, audio_format, audio_quality
            ),
            timeout=180
        )
        return Path(result) if result else None
    except asyncio.TimeoutError:
        logger.error("YouTube download timed out")
        return None
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None


def _download_by_url_sync(url: str, output_dir: Path, audio_format: str, audio_quality: str) -> Optional[str]:
    """Synchronous download from specific URL using yt-dlp module."""
    yt_dlp = _get_ytdlp()
    if not yt_dlp:
        return None
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': audio_quality,
        }],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    # Add cookies if available
    cookies_path = _get_cookies_path()
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    
    logger.info(f"Downloading from URL: {url}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            
            if result:
                title = result.get('title', 'download')
                # Clean title for filename
                safe_title = re.sub(r'[<>:"/\\|?*]', '', title)[:100]
                
                # Find the downloaded file
                for ext in [audio_format, 'mp3', 'm4a', 'opus', 'webm']:
                    potential_file = output_dir / f"{safe_title}.{ext}"
                    if potential_file.exists():
                        logger.info(f"Downloaded: {potential_file}")
                        return str(potential_file)
                
                # Try glob match
                for f in output_dir.glob(f"*{result.get('id', '')}*"):
                    if f.suffix.lower() in ['.mp3', '.m4a', '.opus', '.webm', '.flac']:
                        return str(f)
                
                # Last resort - find most recent audio file
                audio_files = sorted(
                    [f for f in output_dir.glob("*") if f.suffix.lower() in ['.mp3', '.m4a', '.opus', '.webm', '.flac']],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if audio_files:
                    return str(audio_files[0])
            
            logger.warning("Downloaded file not found")
            return None
            
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None


async def download_by_url(
    url: str,
    output_dir: Path = None,
    audio_format: str = "mp3",
    audio_quality: str = "128"
) -> Optional[Path]:
    """
    Download audio from a specific YouTube URL.
    """
    if output_dir is None:
        output_dir = config.AUDIO_DIR
    
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                _download_by_url_sync,
                url, output_dir, audio_format, audio_quality
            ),
            timeout=180
        )
        return Path(result) if result else None
    except asyncio.TimeoutError:
        logger.error("YouTube download timed out")
        return None
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None
