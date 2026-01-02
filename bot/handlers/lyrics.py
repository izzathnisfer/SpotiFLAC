"""
Lyrics Handler - Download lyrics for tracks
"""

import os
from pathlib import Path

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

import config
from services import backend
from handlers.download import parse_spotify_url, _user_sessions


async def handle(client: Client, message: Message):
    """Handle /lyrics <url> command."""
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.reply("Usage: /lyrics <spotify_track_url>")
        return
    
    url = parts[1].strip()
    url_type, spotify_id = parse_spotify_url(url)
    
    if url_type != "track":
        await message.reply("❌ Please provide a Spotify track URL")
        return
    
    status_msg = await message.reply("🎤 Fetching lyrics...")
    
    # Get metadata first
    api = backend.get_client()
    metadata = await api.get_metadata(url)
    
    if "error" in metadata:
        await status_msg.edit_text(f"❌ Error: {metadata['error']}")
        return
    
    track = metadata.get("track", {})
    
    await status_msg.edit_text(f"🎤 Downloading lyrics for:\n**{track.get('name')}**")
    
    result = await api.download_lyrics(
        spotify_id=track.get("spotify_id", ""),
        track_name=track.get("name", ""),
        artist_name=track.get("artists", "")
    )
    
    if not result.get("success"):
        await status_msg.edit_text(f"❌ {result.get('error', 'Failed to get lyrics')}")
        return
    
    file_path = result.get("file", "")
    if file_path and Path(file_path).exists():
        await client.send_document(
            chat_id=message.chat.id,
            document=file_path,
            caption=f"🎤 **{track.get('name')}**\n👤 {track.get('artists')}"
        )
        await status_msg.delete()
        os.remove(file_path)
    else:
        await status_msg.edit_text("❌ Lyrics file not found")


async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle lyrics button callback."""
    data = callback.data
    user_id = callback.from_user.id
    spotify_id = data[4:]  # Remove "lyr:" prefix
    
    # Get track from session
    session = _user_sessions.get(user_id, {})
    track = None
    for t in session.get("tracks", {}).values():
        if t.get("spotify_id") == spotify_id:
            track = t
            break
    
    if not track:
        await callback.answer("❌ Track data not found", show_alert=True)
        return
    
    await callback.answer("🎤 Downloading lyrics...")
    
    api = backend.get_client()
    result = await api.download_lyrics(
        spotify_id=spotify_id,
        track_name=track.get("name", ""),
        artist_name=track.get("artists", "")
    )
    
    if not result.get("success"):
        await callback.message.reply(f"❌ {result.get('error', 'Failed to get lyrics')}")
        return
    
    file_path = result.get("file", "")
    if file_path and Path(file_path).exists():
        await client.send_document(
            chat_id=callback.message.chat.id,
            document=file_path,
            caption=f"🎤 **{track.get('name')}**\n👤 {track.get('artists')}"
        )
        os.remove(file_path)
    else:
        await callback.message.reply("❌ Lyrics file not found")
