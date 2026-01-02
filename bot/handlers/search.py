"""
Search Handler - Search Spotify for tracks/albums/artists
"""

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services import backend


async def handle(client: Client, message: Message):
    """Handle /search <query> command."""
    parts = message.text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.reply(
            "🔍 **Search Spotify**\n\n"
            "Usage: `/search <query>`\n\n"
            "Example: `/search Daft Punk Get Lucky`"
        )
        return
    
    query = parts[1].strip()
    if len(query) < 2:
        await message.reply("❌ Query too short. Please enter at least 2 characters.")
        return
    
    status_msg = await message.reply(f"🔍 Searching for: **{query}**...")
    
    # Call backend search
    api = backend.get_client()
    results = await api.search(query, limit=10)
    
    if "error" in results:
        await status_msg.edit_text(f"❌ Error: {results['error']}")
        return
    
    # Format results
    text, keyboard = format_search_results(query, results)
    await status_msg.edit_text(text, reply_markup=keyboard)


def format_search_results(query: str, results: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Format search results with inline keyboard."""
    
    tracks = results.get("tracks", [])[:5]
    albums = results.get("albums", [])[:3]
    artists = results.get("artists", [])[:2]
    
    text = f"🔍 **Results for:** `{query}`\n\n"
    buttons = []
    
    # Tracks
    if tracks:
        text += "**🎵 Tracks:**\n"
        for i, track in enumerate(tracks, 1):
            name = track.get("name", "Unknown")[:30]
            artist = track.get("artists", "Unknown")[:20]
            text += f"  {i}. {name} - {artist}\n"
            buttons.append([InlineKeyboardButton(
                f"🎵 {name[:25]}",
                callback_data=f"src:t:{track.get('id', '')}"
            )])
        text += "\n"
    
    # Albums
    if albums:
        text += "**💿 Albums:**\n"
        for album in albums:
            name = album.get("name", "Unknown")[:30]
            artist = album.get("artists", "Unknown")[:20]
            text += f"  • {name} - {artist}\n"
            buttons.append([InlineKeyboardButton(
                f"💿 {name[:25]}",
                callback_data=f"src:a:{album.get('id', '')}"
            )])
        text += "\n"
    
    # Artists
    if artists:
        text += "**🎤 Artists:**\n"
        for artist in artists:
            name = artist.get("name", "Unknown")[:30]
            text += f"  • {name}\n"
            buttons.append([InlineKeyboardButton(
                f"🎤 {name[:25]}",
                callback_data=f"src:r:{artist.get('id', '')}"
            )])
    
    if not tracks and not albums and not artists:
        text = f"🔍 No results found for: `{query}`"
    
    return text, InlineKeyboardMarkup(buttons) if buttons else None


async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle search result selection."""
    data = callback.data
    
    if data.startswith("src:t:"):
        # Selected a track - fetch and show track info
        track_id = data[6:]
        url = f"https://open.spotify.com/track/{track_id}"
        
        await callback.answer("Loading track...")
        
        # Import here to avoid circular import
        from handlers import download
        
        # Create a fake message with the URL
        class FakeMessage:
            def __init__(self, text, from_user, reply):
                self.text = text
                self.from_user = from_user
                self._reply = reply
            
            async def reply(self, text):
                return await self._reply(text)
        
        fake_msg = FakeMessage(
            url,
            callback.from_user,
            callback.message.reply
        )
        await download.handle_url(client, fake_msg)
    
    elif data.startswith("src:a:"):
        # Selected an album
        album_id = data[6:]
        url = f"https://open.spotify.com/album/{album_id}"
        await callback.answer("Loading album...")
        
        from handlers import download
        
        class FakeMessage:
            def __init__(self, text, from_user, reply):
                self.text = text
                self.from_user = from_user
                self._reply = reply
            
            async def reply(self, text):
                return await self._reply(text)
        
        fake_msg = FakeMessage(
            url,
            callback.from_user,
            callback.message.reply
        )
        await download.handle_url(client, fake_msg)
    
    elif data.startswith("src:r:"):
        # Selected an artist
        artist_id = data[6:]
        url = f"https://open.spotify.com/artist/{artist_id}"
        await callback.answer("Loading artist...")
        
        from handlers import download
        
        class FakeMessage:
            def __init__(self, text, from_user, reply):
                self.text = text
                self.from_user = from_user
                self._reply = reply
            
            async def reply(self, text):
                return await self._reply(text)
        
        fake_msg = FakeMessage(
            url,
            callback.from_user,
            callback.message.reply
        )
        await download.handle_url(client, fake_msg)
