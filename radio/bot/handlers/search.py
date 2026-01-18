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
    Download a track using SpotiFLAC API.
    Returns the path to the downloaded file.
    """
    try:
        isrc = track_data.get("isrc", "")
        if not isrc:
            logger.warning(f"No ISRC for track: {track_data.get('name')}")
            return None
        
        # Prepare download request
        download_request = {
            "isrc": isrc,
            "service": "tidal",  # Default to Tidal
            "track_name": track_data.get("name", ""),
            "artist_name": track_data.get("artists", ""),
            "album_name": track_data.get("album", ""),
            "quality": "flac",
            "output_dir": str(config.AUDIO_DIR),
            "embed_lyrics": False,
            "embed_max_quality_cover": False
        }
        
        async with httpx.AsyncClient(timeout=180) as http:
            response = await http.post(
                f"{config.SPOTIFLAC_API_URL}/download",
                json=download_request
            )
            
            if response.status_code != 200:
                logger.error(f"Download API error: {response.status_code}")
                return None
            
            result = response.json()
            
            if result.get("success"):
                file_path = result.get("file")
                if file_path:
                    return Path(file_path)
        
        return None
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None


async def handle_search_query(client: Client, message: Message):
    """Handle search text when in add mode."""
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
    
    # Perform search
    msg = await message.reply("🔍 Searching...", quote=True)
    
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(
                f"{config.SPOTIFLAC_API_URL}/search",
                params={"query": query, "limit": 5}
            )
            
            if response.status_code != 200:
                await msg.edit_text("❌ Search failed")
                return
            
            data = response.json()
            tracks = data.get("tracks", [])
            
            if not tracks:
                await msg.edit_text("❌ No results found")
                return
            
            # Cache results
            _search_cache[user_id] = tracks
            
            text = f"🔍 **Search Results for:** `{query}`\n\n"
            for i, track in enumerate(tracks[:5], 1):
                text += f"{i}. **{track.get('name', 'Unknown')}**\n"
                text += f"   🎤 {track.get('artists', 'Unknown')}\n\n"
            
            await msg.edit_text(
                text,
                reply_markup=search_results_keyboard(tracks, page=0, total_pages=1)
            )
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await msg.edit_text(f"❌ Search error: {e}")


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
        # Add selected track
        track_id = parts[2] if len(parts) > 2 else ""
        tracks = _search_cache.get(user_id, [])
        
        track_data = next((t for t in tracks if t.get("spotify_id") == track_id), None)
        if not track_data:
            await callback.answer("Track not found", show_alert=True)
            return
        
        await callback.answer("⏳ Adding track...")
        await callback.message.edit_text("⏳ Downloading track...")
        
        try:
            await add_track_to_queue(player, track_data, callback.message)
            exit_add_mode(user_id)
        except Exception as e:
            await callback.message.edit_text(f"❌ Failed: {e}")
            
    elif action == "page":
        page = int(parts[2]) if len(parts) > 2 else 0
        tracks = _search_cache.get(user_id, [])
        
        await callback.message.edit_reply_markup(
            reply_markup=search_results_keyboard(tracks, page=page, total_pages=1)
        )
        await callback.answer()
