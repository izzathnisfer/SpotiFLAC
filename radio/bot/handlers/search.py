"""
Radio Bot - Search & Add Handlers

Handles Spotify link detection and search functionality.
"""

import logging
import re
import uuid
import httpx
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from bot.keyboards import search_results_keyboard, radio_controls_keyboard, back_keyboard
from bot.handlers.radio import is_in_add_mode, exit_add_mode
from core.player import get_player
from core.queue_manager import Track
import config

logger = logging.getLogger(__name__)

# Spotify URL regex
SPOTIFY_REGEX = re.compile(
    r'https?://open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)'
)

# Store search results temporarily
_search_cache: dict[int, list] = {}


async def handle_spotify_link(client: Client, message: Message):
    """Handle incoming Spotify links."""
    user_id = message.from_user.id
    text = message.text or ""
    
    # Check if user has an active session
    player = get_player(str(user_id))
    if not player:
        await message.reply(
            "⚠️ Start your radio first!\n\nUse /start to begin.",
            quote=True
        )
        return
    
    # Parse Spotify URL
    match = SPOTIFY_REGEX.search(text)
    if not match:
        return
    
    content_type = match.group(1)  # track, album, playlist
    content_id = match.group(2)
    
    logger.info(f"Spotify {content_type}: {content_id} from {user_id}")
    
    # Send processing message
    msg = await message.reply(f"⏳ Processing {content_type}...", quote=True)
    
    try:
        # Fetch metadata from SpotiFLAC API
        async with httpx.AsyncClient(timeout=60) as http:
            response = await http.get(
                f"{config.SPOTIFLAC_API_URL}/metadata",
                params={"url": text}
            )
            
            if response.status_code != 200:
                await msg.edit_text(f"❌ Failed to fetch metadata: {response.status_code}")
                return
            
            data = response.json()
        
        if content_type == "track":
            # Single track
            track_data = data.get("track") or data
            await add_track_to_queue(player, track_data, msg)
            
        elif content_type == "album":
            # Album - add all tracks
            tracks = data.get("tracks", [])
            if not tracks:
                await msg.edit_text("❌ No tracks found in album")
                return
            
            added = 0
            for track_data in tracks:
                try:
                    await add_track_to_queue(player, track_data, None)
                    added += 1
                except Exception as e:
                    logger.error(f"Failed to add track: {e}")
            
            await msg.edit_text(
                f"✅ Added {added} tracks from album!",
                reply_markup=radio_controls_keyboard()
            )
            
        elif content_type == "playlist":
            # Playlist - add all tracks
            tracks = data.get("tracks", [])
            if not tracks:
                await msg.edit_text("❌ No tracks found in playlist")
                return
            
            added = 0
            for track_data in tracks[:50]:  # Limit to 50 tracks
                try:
                    await add_track_to_queue(player, track_data, None)
                    added += 1
                except Exception as e:
                    logger.error(f"Failed to add track: {e}")
            
            extra = len(tracks) - 50 if len(tracks) > 50 else 0
            extra_text = f"\n_(Limited to 50, {extra} skipped)_" if extra else ""
            
            await msg.edit_text(
                f"✅ Added {added} tracks from playlist!{extra_text}",
                reply_markup=radio_controls_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error processing Spotify link: {e}")
        await msg.edit_text(f"❌ Error: {e}")


async def add_track_to_queue(player, track_data: dict, msg: Message = None):
    """Add a track to the player's queue."""
    # Create track object
    track = Track(
        id=str(uuid.uuid4())[:8],
        file_path=Path("/tmp/placeholder.mp3"),  # Will be replaced by actual download
        title=track_data.get("name", "Unknown"),
        artist=track_data.get("artists", "Unknown"),
        album=track_data.get("album", "Unknown"),
        spotify_id=track_data.get("spotify_id", ""),
        isrc=track_data.get("isrc", ""),
        added_by=player.owner_id
    )
    
    # For now, we'll use a simple download approach
    # In production, this would call the SpotiFLAC download API
    downloaded_path = await download_track(track_data)
    
    if downloaded_path:
        track.file_path = downloaded_path
        await player.add_track(track)
        
        if msg:
            await msg.edit_text(
                f"✅ Added to queue!\n\n🎵 **{track.title}**\n🎤 {track.artist}",
                reply_markup=radio_controls_keyboard()
            )
    else:
        if msg:
            await msg.edit_text(f"❌ Failed to download: {track.title}")


async def download_track(track_data: dict) -> Path | None:
    """
    Download a track. Tries SpotiFLAC API first, then falls back to yt-dlp.
    Returns the path to the downloaded file.
    """
    track_name = track_data.get("name", "Unknown")
    artist_name = track_data.get("artists", "Unknown")
    
    # Try SpotiFLAC first (if we have ISRC)
    isrc = track_data.get("isrc", "")
    if isrc:
        logger.info(f"Trying SpotiFLAC for: {artist_name} - {track_name}")
        try:
            download_request = {
                "isrc": isrc,
                "source": "auto",
                "track_name": track_name,
                "artist_name": artist_name,
                "album_name": track_data.get("album", ""),
                "quality": "LOSSLESS",
                "output_dir": str(config.AUDIO_DIR),
            }
            
            async with httpx.AsyncClient(timeout=120) as http:
                response = await http.post(
                    f"{config.SPOTIFLAC_API_URL}/download",
                    json=download_request
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        file_path = result.get("file")
                        if file_path and Path(file_path).exists():
                            logger.info(f"SpotiFLAC download success: {file_path}")
                            return Path(file_path)
                
                logger.warning(f"SpotiFLAC failed, trying yt-dlp fallback")
                
        except Exception as e:
            logger.warning(f"SpotiFLAC error: {e}, trying yt-dlp fallback")
    
    # Fallback to yt-dlp (YouTube Music)
    logger.info(f"Using yt-dlp for: {artist_name} - {track_name}")
    try:
        from core.ytdlp_downloader import download_from_youtube
        
        search_query = f"{artist_name} - {track_name}"
        downloaded_path = await download_from_youtube(
            query=search_query,
            output_dir=config.AUDIO_DIR,
            audio_format="mp3",
            audio_quality=str(config.AUDIO_BITRATE)
        )
        
        if downloaded_path:
            logger.info(f"yt-dlp download success: {downloaded_path}")
            return downloaded_path
            
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
    
    return None


async def handle_search_query(client: Client, message: Message):
    """Handle search text when in add mode. Searches both Spotify and YouTube."""
    user_id = message.from_user.id
    
    if not is_in_add_mode(user_id):
        return
    
    player = get_player(str(user_id))
    if not player:
        exit_add_mode(user_id)
        return
    
    query = message.text.strip()
    if not query or len(query) < 2:
        return
    
    # Check if it's a Spotify link
    if SPOTIFY_REGEX.search(query):
        await handle_spotify_link(client, message)
        exit_add_mode(user_id)
        return
    
    # Perform dual search (Spotify + YouTube)
    msg = await message.reply("🔍 Searching Spotify & YouTube...", quote=True)
    
    spotify_results = []
    youtube_results = []
    
    # Search Spotify (with error handling)
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.get(
                f"{config.SPOTIFLAC_API_URL}/search",
                params={"query": query, "limit": 5}
            )
            if response.status_code == 200:
                data = response.json()
                if "error" not in data:
                    spotify_results = data.get("tracks", [])[:5]
    except Exception as e:
        logger.warning(f"Spotify search failed: {e}")
    
    # Search YouTube (with error handling)
    try:
        from core.ytdlp_downloader import search_youtube
        yt_results = await search_youtube(query, max_results=5)
        for r in yt_results:
            youtube_results.append({
                "name": r.get("title", "Unknown"),
                "artists": r.get("channel", "YouTube"),
                "duration": r.get("duration", 0),
                "youtube_url": r.get("url", ""),
                "source": "youtube"
            })
    except Exception as e:
        logger.warning(f"YouTube search failed: {e}")
    
    # Combine results
    all_results = []
    
    # Add Spotify results with source tag
    for track in spotify_results:
        track["source"] = "spotify"
        all_results.append(track)
    
    # Add YouTube results
    all_results.extend(youtube_results)
    
    if not all_results:
        await msg.edit_text("❌ No results found. Please try a different search.")
        return
    
    # Cache all results
    _search_cache[user_id] = all_results
    
    # Build results text
    text = f"🔍 **Results for:** `{query}`\n\n"
    
    if spotify_results:
        text += "🎵 **Spotify:**\n"
        for i, track in enumerate(spotify_results[:5], 1):
            text += f"  {i}. {track.get('name', 'Unknown')[:30]}\n"
            text += f"      🎤 {track.get('artists', 'Unknown')[:25]}\n"
        text += "\n"
    
    if youtube_results:
        text += "📺 **YouTube:**\n"
        offset = len(spotify_results)
        for i, track in enumerate(youtube_results[:5], 1):
            text += f"  {offset + i}. {track.get('name', 'Unknown')[:30]}\n"
            text += f"      📺 {track.get('artists', 'Unknown')[:25]}\n"
    
    await msg.edit_text(
        text,
        reply_markup=search_results_keyboard(all_results, page=0, total_pages=1)
    )


async def handle_search_callback(client: Client, callback: CallbackQuery):
    """Handle search:* callbacks."""
    user_id = callback.from_user.id
    data = callback.data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active session", show_alert=True)
        return
    
    if action == "add":
        # Add selected track by index
        try:
            track_idx = int(parts[2]) if len(parts) > 2 else 0
            tracks = _search_cache.get(user_id, [])
            
            if track_idx < 0 or track_idx >= len(tracks):
                await callback.answer("Track not found", show_alert=True)
                return
            
            track_data = tracks[track_idx]
            source = track_data.get("source", "spotify")
            
            await callback.answer("⏳ Downloading...")
            await callback.message.edit_text("⏳ Downloading track...")
            
            # For all sources, use search-based download (SoundCloud works from AWS)
            track_name = track_data.get("name", "Unknown")
            artist_name = track_data.get("artists", "Unknown")
            search_query = f"{artist_name} - {track_name}"
            
            from core.ytdlp_downloader import download_from_youtube
            downloaded_path = await download_from_youtube(
                query=search_query,
                output_dir=config.AUDIO_DIR,
                audio_format="mp3",
                audio_quality=str(config.AUDIO_BITRATE)
            )
            
            if downloaded_path:
                from core.queue_manager import Track
                track = Track(
                    id=str(uuid.uuid4())[:8],
                    file_path=downloaded_path,
                    title=track_name,
                    artist=artist_name,
                    added_by=player.owner_id
                )
                await player.add_track(track)
                source_icon = "🎵" if source == "spotify" else "📺"
                await callback.message.edit_text(
                    f"✅ Added!\n\n{source_icon} **{track.title}**\n🎤 {track.artist}",
                    reply_markup=radio_controls_keyboard()
                )
                exit_add_mode(user_id)
            else:
                await callback.message.edit_text(f"❌ Download failed for: {track_name}")
                
        except Exception as e:
            logger.error(f"Search callback error: {e}")
            await callback.message.edit_text(f"❌ Error: {e}")
            
    elif action == "page":
        page = int(parts[2]) if len(parts) > 2 else 0
        tracks = _search_cache.get(user_id, [])
        
        await callback.message.edit_reply_markup(
            reply_markup=search_results_keyboard(tracks, page=page, total_pages=1)
        )
        await callback.answer()
