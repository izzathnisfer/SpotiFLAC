"""
Download Handler - Handle Spotify URLs and download tracks
"""

import re
import os
import logging
import time
from pathlib import Path
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import config
from services import database, backend

logger = logging.getLogger(__name__)

# Spotify URL regex
SPOTIFY_URL_RE = re.compile(
    r"(?:https?://)?(?:open\.)?spotify\.com/(track|album|playlist|artist)/([a-zA-Z0-9]+)"
)


def parse_spotify_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Parse Spotify URL and return (type, id)."""
    match = SPOTIFY_URL_RE.search(url)
    if match:
        return match.group(1), match.group(2)
    return None, None


# =============================================================================
# URL Detection Handler
# =============================================================================

async def handle_url(client: Client, message: Message):
    """Handle a Spotify URL sent by user."""
    url_type, spotify_id = parse_spotify_url(message.text)
    
    if not url_type:
        await message.reply("❌ Invalid Spotify URL")
        return
    
    # Show loading message
    status_msg = await message.reply("🔍 Fetching metadata...")
    
    # Get metadata from backend
    api = backend.get_client()
    metadata = await api.get_metadata(message.text)
    
    if "error" in metadata:
        await status_msg.edit_text(f"❌ Error: {metadata['error']}")
        return
    
    # Handle based on type
    if url_type == "track":
        await handle_track_metadata(client, status_msg, metadata, message.from_user.id)
    elif url_type == "album":
        await handle_album_metadata(client, status_msg, metadata, message.from_user.id)
    elif url_type == "playlist":
        await handle_playlist_metadata(client, status_msg, metadata, message.from_user.id)
    elif url_type == "artist":
        await handle_artist_metadata(client, status_msg, metadata, message.from_user.id)


# =============================================================================
# Track Display
# =============================================================================

async def handle_track_metadata(
    client: Client,
    status_msg: Message,
    metadata: dict,
    user_id: int
):
    """Display track info with action buttons."""
    track = metadata.get("track", {})
    
    text = f"""
🎵 **{track.get('name', 'Unknown')}**

👤 {track.get('artists', 'Unknown Artist')}
💿 {track.get('album', 'Unknown Album')}
📅 {track.get('release_date', 'N/A')}
⏱ {format_duration(track.get('duration_ms', 0))}
🔖 ISRC: `{track.get('isrc', 'N/A')}`
"""
    
    # Create action buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬇️ Download FLAC",
                callback_data=f"dl:t:{track.get('isrc', '')}"
            )
        ],
        [
            InlineKeyboardButton("🎤 Lyrics", callback_data=f"lyr:{track.get('spotify_id', '')}"),
            InlineKeyboardButton("🖼️ Cover", callback_data=f"cov:{track.get('spotify_id', '')}"),
        ],
        [
            InlineKeyboardButton("🔍 Check Availability", callback_data=f"chk:{track.get('spotify_id', '')}")
        ]
    ])
    
    # Store track data in user session for later use
    await store_track_session(user_id, track.get('isrc', ''), track)
    
    await status_msg.edit_text(text, reply_markup=keyboard)


# =============================================================================
# Album Display
# =============================================================================

async def handle_album_metadata(
    client: Client,
    status_msg: Message,
    metadata: dict,
    user_id: int
):
    """Display album info with track selection."""
    album = metadata.get("album_info", {})
    tracks = metadata.get("track_list", [])
    
    total_duration = sum(t.get('duration_ms', 0) for t in tracks)
    
    text = f"""
💿 **{album.get('name', 'Unknown Album')}**

👤 {album.get('artists', 'Unknown Artist')}
📅 {album.get('release_date', 'N/A')}
🎵 {len(tracks)} tracks • {format_duration(total_duration)}
"""
    
    # Store tracks for session
    await store_album_session(user_id, album, tracks)
    
    # Create track list with checkboxes (page 1)
    keyboard = create_track_selection_keyboard(tracks, set(), 0, user_id, "album")
    
    await status_msg.edit_text(text, reply_markup=keyboard)


# =============================================================================
# Playlist Display
# =============================================================================

async def handle_playlist_metadata(
    client: Client,
    status_msg: Message,
    metadata: dict,
    user_id: int
):
    """Display playlist info with track selection."""
    playlist = metadata.get("playlist_info", {})
    tracks = metadata.get("track_list", [])
    
    owner = playlist.get("owner", {})
    total_duration = sum(t.get('duration_ms', 0) for t in tracks)
    
    text = f"""
📋 **{owner.get('name', 'Playlist')}**

👤 by {owner.get('display_name', 'Unknown')}
🎵 {len(tracks)} tracks • {format_duration(total_duration)}
"""
    
    await store_album_session(user_id, playlist, tracks)
    keyboard = create_track_selection_keyboard(tracks, set(), 0, user_id, "playlist")
    
    await status_msg.edit_text(text, reply_markup=keyboard)


# =============================================================================
# Artist Display
# =============================================================================

async def handle_artist_metadata(
    client: Client,
    status_msg: Message,
    metadata: dict,
    user_id: int
):
    """Display artist info with album list."""
    artist = metadata.get("artist_info", {})
    albums = metadata.get("album_list", [])
    tracks = metadata.get("track_list", [])
    
    text = f"""
🎤 **{artist.get('name', 'Unknown Artist')}**

💿 {len(albums)} albums
🎵 {len(tracks)} total tracks
"""
    
    # For artist, show album selection first
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"💿 {a.get('name', 'Album')[:30]}",
            callback_data=f"album:{a.get('spotify_id', '')}"
        )] for a in albums[:10]
    ] + [
        [InlineKeyboardButton("⬇️ Download All Tracks", callback_data=f"dl:artist:all")]
    ])
    
    await store_album_session(user_id, artist, tracks)
    await status_msg.edit_text(text, reply_markup=keyboard)


# =============================================================================
# Callback Handlers
# =============================================================================

async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle download button callbacks."""
    data = callback.data
    user_id = callback.from_user.id
    
    if data.startswith("dl:t:"):
        # Single track download
        isrc = data[5:]
        await download_single_track(client, callback, isrc, user_id)
    
    elif data.startswith("dl:sel"):
        # Download selected tracks
        await download_selected_tracks(client, callback, user_id)
    
    elif data.startswith("dl:all"):
        # Download all tracks
        await download_all_tracks(client, callback, user_id)
    
    await callback.answer()


async def handle_selection_callback(client: Client, callback: CallbackQuery):
    """Handle track selection callbacks."""
    data = callback.data
    user_id = callback.from_user.id
    
    if data.startswith("sel:"):
        # Toggle track selection
        isrc = data[4:]
        await toggle_track_selection(client, callback, isrc, user_id)
    
    elif data.startswith("page:"):
        # Change page
        page = int(data[5:])
        await change_page(client, callback, page, user_id)
    
    elif data == "selall":
        await select_all_tracks(client, callback, user_id)
    
    elif data == "clear":
        await clear_selection(client, callback, user_id)


# =============================================================================
# Download Functions
# =============================================================================

async def download_single_track(
    client: Client,
    callback: CallbackQuery,
    isrc: str,
    user_id: int
):
    """Download a single track."""
    
    # Check cache first
    cached = await database.get_cached_file(isrc)
    if cached:
        # Forward from cache channel (instant!)
        await client.forward_messages(
            chat_id=user_id,
            from_chat_id=config.CACHE_CHANNEL_ID,
            message_ids=cached['message_id']
        )
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ **Sent from cache!**"
        )
        return
    
    # Get track data from session
    track = await get_track_from_session(user_id, isrc)
    if not track:
        await callback.answer("❌ Track data not found. Please try again.", show_alert=True)
        return
    
    # Get user settings
    settings = await database.get_user_settings(user_id)
    
    # Update message to show progress
    progress_msg = await callback.message.edit_text(
        callback.message.text + "\n\n⬇️ **Downloading...**\n⏳ Please wait..."
    )
    
    # Call backend to download
    api = backend.get_client()
    result = await api.download_track(
        isrc=track.get('isrc', ''),
        spotify_id=track.get('spotify_id', ''),
        track_name=track.get('name', ''),
        artist_name=track.get('artists', ''),
        album_name=track.get('album', ''),
        album_artist=track.get('album_artist', ''),
        release_date=track.get('release_date', ''),
        cover_url=track.get('images', ''),
        track_number=track.get('track_number', 0),
        disc_number=track.get('disc_number', 0),
        total_tracks=track.get('total_tracks', 0),
        source=settings.get('source', 'auto'),
        quality=settings.get('tidal_quality', 'LOSSLESS'),
        embed_lyrics=settings.get('embed_lyrics', 0) == 1,
        embed_max_cover=settings.get('embed_max_cover', 1) == 1
    )
    
    if not result.get('success'):
        await progress_msg.edit_text(
            callback.message.text + f"\n\n❌ **Download failed:**\n{result.get('error', 'Unknown error')}"
        )
        return
    
    file_path = result.get('file', '')
    if not file_path or not Path(file_path).exists():
        await progress_msg.edit_text(
            callback.message.text + "\n\n❌ **File not found after download**"
        )
        return
    
    # Upload to cache channel with progress
    await progress_msg.edit_text(
        callback.message.text + "\n\n⬆️ **Uploading to Telegram...**"
    )
    
    caption = f"🎵 {track.get('name', 'Track')}\n👤 {track.get('artists', 'Artist')}\n💿 {track.get('album', 'Album')}"
    
    last_update = [0]  # Use list to allow mutation in closure
    
    async def upload_progress(current, total):
        """Callback for upload progress."""
        now = time.time()
        if now - last_update[0] < config.PROGRESS_UPDATE_INTERVAL:
            return
        last_update[0] = now
        
        percent = current * 100 / total
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        
        progress_bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
        
        try:
            await progress_msg.edit_text(
                callback.message.text + 
                f"\n\n⬆️ **Uploading...**\n"
                f"{progress_bar} {percent:.1f}%\n"
                f"{mb_current:.1f} MB / {mb_total:.1f} MB"
            )
        except:
            pass  # Ignore rate limit errors
    
    try:
        # Upload to cache channel
        cache_msg = await client.send_document(
            chat_id=config.CACHE_CHANNEL_ID,
            document=file_path,
            caption=caption,
            progress=upload_progress
        )
        
        # Store in database
        file_size = Path(file_path).stat().st_size
        await database.cache_file(
            isrc=isrc,
            file_id=cache_msg.document.file_id,
            message_id=cache_msg.id,
            file_name=Path(file_path).name,
            file_size=file_size,
            quality=settings.get('tidal_quality', 'LOSSLESS'),
            source=settings.get('source', 'auto')
        )
        
        # Forward to user
        await client.forward_messages(
            chat_id=user_id,
            from_chat_id=config.CACHE_CHANNEL_ID,
            message_ids=cache_msg.id
        )
        
        # Update message
        await progress_msg.edit_text(
            callback.message.text + "\n\n✅ **Downloaded successfully!**"
        )
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await progress_msg.edit_text(
            callback.message.text + f"\n\n❌ **Upload failed:** {str(e)}"
        )
    finally:
        # Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass


# =============================================================================
# Session Storage (in-memory for now, could use Redis)
# =============================================================================

_user_sessions: dict = {}


async def store_track_session(user_id: int, isrc: str, track: dict):
    """Store track data in user session."""
    if user_id not in _user_sessions:
        _user_sessions[user_id] = {"tracks": {}, "selected": set(), "page": 0}
    _user_sessions[user_id]["tracks"][isrc] = track


async def store_album_session(user_id: int, album: dict, tracks: list):
    """Store album/playlist data in user session."""
    if user_id not in _user_sessions:
        _user_sessions[user_id] = {"tracks": {}, "selected": set(), "page": 0}
    
    _user_sessions[user_id]["album"] = album
    _user_sessions[user_id]["track_list"] = tracks
    _user_sessions[user_id]["selected"] = set()
    _user_sessions[user_id]["page"] = 0
    
    # Store each track by ISRC
    for t in tracks:
        if t.get('isrc'):
            _user_sessions[user_id]["tracks"][t['isrc']] = t


async def get_track_from_session(user_id: int, isrc: str) -> Optional[dict]:
    """Get track data from session."""
    session = _user_sessions.get(user_id, {})
    return session.get("tracks", {}).get(isrc)


# =============================================================================
# Track Selection Keyboard
# =============================================================================

def create_track_selection_keyboard(
    tracks: list,
    selected: set,
    page: int,
    user_id: int,
    context: str = "album"
) -> InlineKeyboardMarkup:
    """Create paginated track selection keyboard."""
    per_page = config.TRACKS_PER_PAGE
    start = page * per_page
    end = start + per_page
    page_tracks = tracks[start:end]
    total_pages = (len(tracks) + per_page - 1) // per_page
    
    buttons = []
    
    # Track buttons with checkboxes
    for i, track in enumerate(page_tracks, start=start+1):
        isrc = track.get('isrc', '')
        icon = "✅" if isrc in selected else "⬜"
        name = track.get('name', 'Unknown')[:25]
        buttons.append([InlineKeyboardButton(
            f"{icon} {i}. {name}",
            callback_data=f"sel:{isrc}"
        )])
    
    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"page:{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if end < len(tracks):
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"page:{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    
    # Selection row
    buttons.append([
        InlineKeyboardButton("Select All", callback_data="selall"),
        InlineKeyboardButton("Clear", callback_data="clear"),
    ])
    
    # Download row
    buttons.append([
        InlineKeyboardButton(f"⬇️ Download ({len(selected)})", callback_data="dl:sel"),
        InlineKeyboardButton("⬇️ All", callback_data="dl:all"),
    ])
    
    return InlineKeyboardMarkup(buttons)


async def toggle_track_selection(client: Client, callback: CallbackQuery, isrc: str, user_id: int):
    """Toggle track selection."""
    session = _user_sessions.get(user_id, {})
    selected = session.get("selected", set())
    
    if isrc in selected:
        selected.discard(isrc)
    else:
        selected.add(isrc)
    
    session["selected"] = selected
    _user_sessions[user_id] = session
    
    # Refresh keyboard
    tracks = session.get("track_list", [])
    page = session.get("page", 0)
    keyboard = create_track_selection_keyboard(tracks, selected, page, user_id)
    
    await callback.message.edit_reply_markup(keyboard)
    await callback.answer()


async def change_page(client: Client, callback: CallbackQuery, page: int, user_id: int):
    """Change page in track list."""
    session = _user_sessions.get(user_id, {})
    session["page"] = page
    _user_sessions[user_id] = session
    
    tracks = session.get("track_list", [])
    selected = session.get("selected", set())
    keyboard = create_track_selection_keyboard(tracks, selected, page, user_id)
    
    await callback.message.edit_reply_markup(keyboard)
    await callback.answer()


async def select_all_tracks(client: Client, callback: CallbackQuery, user_id: int):
    """Select all tracks."""
    session = _user_sessions.get(user_id, {})
    tracks = session.get("track_list", [])
    selected = {t.get('isrc') for t in tracks if t.get('isrc')}
    session["selected"] = selected
    _user_sessions[user_id] = session
    
    page = session.get("page", 0)
    keyboard = create_track_selection_keyboard(tracks, selected, page, user_id)
    
    await callback.message.edit_reply_markup(keyboard)
    await callback.answer(f"Selected {len(selected)} tracks")


async def clear_selection(client: Client, callback: CallbackQuery, user_id: int):
    """Clear all selections."""
    session = _user_sessions.get(user_id, {})
    session["selected"] = set()
    _user_sessions[user_id] = session
    
    tracks = session.get("track_list", [])
    page = session.get("page", 0)
    keyboard = create_track_selection_keyboard(tracks, set(), page, user_id)
    
    await callback.message.edit_reply_markup(keyboard)
    await callback.answer("Selection cleared")


async def download_selected_tracks(client: Client, callback: CallbackQuery, user_id: int):
    """Download selected tracks."""
    session = _user_sessions.get(user_id, {})
    selected = session.get("selected", set())
    
    if not selected:
        await callback.answer("No tracks selected!", show_alert=True)
        return
    
    await callback.answer(f"Starting download of {len(selected)} tracks...")
    
    # Download each track sequentially
    for isrc in selected:
        await download_single_track(client, callback, isrc, user_id)


async def download_all_tracks(client: Client, callback: CallbackQuery, user_id: int):
    """Download all tracks."""
    session = _user_sessions.get(user_id, {})
    tracks = session.get("track_list", [])
    
    if not tracks:
        await callback.answer("No tracks found!", show_alert=True)
        return
    
    # Select all and download
    isrcs = [t.get('isrc') for t in tracks if t.get('isrc')]
    await callback.answer(f"Starting download of {len(isrcs)} tracks...")
    
    for isrc in isrcs:
        await download_single_track(client, callback, isrc, user_id)


# =============================================================================
# Utilities
# =============================================================================

def format_duration(ms: int) -> str:
    """Format milliseconds to mm:ss."""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    
    return f"{minutes}:{seconds:02d}"
