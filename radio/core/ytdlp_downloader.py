"""
Radio Service - YT-DLP Downloader

Downloads audio from YouTube as a fallback when SpotiFLAC fails.
Uses yt-dlp to search YouTube and download audio.
"""

import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


def is_ytdlp_available() -> bool:
    """Check if yt-dlp is installed."""
    return shutil.which("yt-dlp") is not None


async def search_youtube(query: str, max_results: int = 5) -> list[dict]:
    """
    Search YouTube for tracks.
    Returns list of results with title, channel, duration, url.
    """
    if not is_ytdlp_available():
        logger.warning("yt-dlp not available")
        return []
    
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-warnings"
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        
        results = []
        for line in stdout.decode().strip().split('\n'):
            if line:
                import json
                try:
                    data = json.loads(line)
                    results.append({
                        "id": data.get("id", ""),
                        "title": data.get("title", "Unknown"),
                        "channel": data.get("channel", data.get("uploader", "Unknown")),
                        "duration": data.get("duration", 0),
                        "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                        "source": "youtube"
                    })
                except json.JSONDecodeError:
                    continue
        
        return results
        
    except asyncio.TimeoutError:
        logger.warning("YouTube search timed out")
        return []
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []


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
    if not is_ytdlp_available():
        logger.error("yt-dlp not installed!")
        return None
    
    if output_dir is None:
        output_dir = config.AUDIO_DIR
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean query for filename
    safe_query = re.sub(r'[<>:"/\\|?*]', '', query)[:100]
    output_template = str(output_dir / f"{safe_query}.%(ext)s")
    
    cmd = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "--extract-audio",
        "--audio-format", audio_format,
        "--audio-quality", f"{audio_quality}k",
        "--output", output_template,
        "--no-playlist",
        "--no-warnings",
        "--quiet"
    ]
    
    logger.info(f"Downloading from YouTube: {query}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(process.communicate(), timeout=120)
        
        if process.returncode != 0:
            logger.error(f"yt-dlp failed with code {process.returncode}")
            return None
        
        # Find the downloaded file
        for ext in [audio_format, 'mp3', 'm4a', 'opus', 'webm']:
            potential_file = output_dir / f"{safe_query}.{ext}"
            if potential_file.exists():
                logger.info(f"Downloaded: {potential_file}")
                return potential_file
        
        # Try to find any recently created audio file
        audio_files = list(output_dir.glob(f"{safe_query}*"))
        if audio_files:
            return audio_files[0]
        
        logger.warning("Downloaded file not found")
        return None
        
    except asyncio.TimeoutError:
        logger.error("YouTube download timed out")
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
    if not is_ytdlp_available():
        logger.error("yt-dlp not installed!")
        return None
    
    if output_dir is None:
        output_dir = config.AUDIO_DIR
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s")
    
    cmd = [
        "yt-dlp",
        url,
        "--extract-audio",
        "--audio-format", audio_format,
        "--audio-quality", f"{audio_quality}k",
        "--output", output_template,
        "--no-playlist",
        "--no-warnings",
        "--print", "after_move:filepath"
    ]
    
    logger.info(f"Downloading from URL: {url}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        
        if process.returncode != 0:
            logger.error(f"yt-dlp failed: {stderr.decode()}")
            return None
        
        # Get the filepath from stdout
        filepath = stdout.decode().strip().split('\n')[-1]
        if filepath and Path(filepath).exists():
            logger.info(f"Downloaded: {filepath}")
            return Path(filepath)
        
        logger.warning("Downloaded file path not found")
        return None
        
    except asyncio.TimeoutError:
        logger.error("YouTube download timed out")
        return None
    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        return None
