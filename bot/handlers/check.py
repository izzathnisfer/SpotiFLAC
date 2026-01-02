"""
Check Handler - Check track availability on platforms
"""

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

from services import backend
from handlers.download import parse_spotify_url, _user_sessions


async def handle(client: Client, message: Message):
    """Handle /check <url> command."""
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.reply("Usage: /check <spotify_track_url>")
        return
    
    url = parts[1].strip()
    url_type, spotify_id = parse_spotify_url(url)
    
    if url_type != "track":
        await message.reply("❌ Please provide a Spotify track URL")
        return
    
    status_msg = await message.reply("🔍 Checking availability...")
    
    # Get metadata first
    api = backend.get_client()
    metadata = await api.get_metadata(url)
    
    if "error" in metadata:
        await status_msg.edit_text(f"❌ Error: {metadata['error']}")
        return
    
    track = metadata.get("track", {})
    
    result = await api.check_availability(
        spotify_id=track.get("spotify_id", ""),
        isrc=track.get("isrc", "")
    )
    
    if "error" in result:
        await status_msg.edit_text(f"❌ Error: {result['error']}")
        return
    
    text = format_availability(track, result)
    await status_msg.edit_text(text)


async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle check availability button callback."""
    data = callback.data
    user_id = callback.from_user.id
    spotify_id = data[4:]  # Remove "chk:" prefix
    
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
    
    await callback.answer("🔍 Checking availability...")
    
    api = backend.get_client()
    result = await api.check_availability(
        spotify_id=spotify_id,
        isrc=track.get("isrc", "")
    )
    
    if "error" in result:
        await callback.message.reply(f"❌ Error: {result['error']}")
        return
    
    text = format_availability(track, result)
    await callback.message.reply(text)


def format_availability(track: dict, availability: dict) -> str:
    """Format availability check results."""
    tidal = "✅" if availability.get("tidal") else "❌"
    qobuz = "✅" if availability.get("qobuz") else "❌"
    amazon = "✅" if availability.get("amazon") else "❌"
    
    text = f"""
🔍 **Availability Check**

🎵 **{track.get('name', 'Unknown')}**
👤 {track.get('artists', 'Unknown')}

**Platforms:**
{tidal} Tidal
{qobuz} Qobuz
{amazon} Amazon Music
"""
    
    # Add URLs if available
    urls = []
    if availability.get("tidal_url"):
        urls.append(f"[Tidal]({availability['tidal_url']})")
    if availability.get("qobuz_url"):
        urls.append(f"[Qobuz]({availability['qobuz_url']})")
    if availability.get("amazon_url"):
        urls.append(f"[Amazon]({availability['amazon_url']})")
    
    if urls:
        text += "\n**Links:** " + " | ".join(urls)
    
    return text
