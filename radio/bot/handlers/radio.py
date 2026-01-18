"""
Radio Bot - Radio Control Handlers

Handles radio control callbacks (start, stop, skip, pause, etc.)
"""

import logging
import uuid
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from bot.keyboards import (
    main_menu_keyboard, 
    radio_controls_keyboard, 
    confirm_stop_keyboard,
    add_mode_keyboard,
    queue_keyboard,
    back_keyboard
)
from core.player import (
    get_player, 
    create_player, 
    remove_player,
    StreamPlayer,
    PlayerState
)
from core.queue_manager import get_queue, remove_queue
import config

logger = logging.getLogger(__name__)

# User state tracking for add mode
_user_add_mode: dict[int, bool] = {}


async def handle_radio_callback(client: Client, callback: CallbackQuery):
    """Handle radio:* callbacks."""
    user = callback.from_user
    user_id = user.id
    username = user.username or user.first_name
    data = callback.data
    
    logger.info(f"Radio callback: {data} from {username} ({user_id})")
    
    # Parse callback data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    
    if action == "start":
        await start_radio(callback, user_id, username)
    elif action == "stop":
        await confirm_stop(callback)
    elif action == "stop:confirm":
        await stop_radio(callback, user_id)
    elif action == "skip":
        await skip_track(callback, user_id)
    elif action == "pause":
        await pause_radio(callback, user_id)
    elif action == "resume":
        await resume_radio(callback, user_id)
    elif action == "status":
        await show_status(callback, user_id)
    elif action == "listeners":
        await show_listeners(callback, user_id)
    elif action == "queue":
        await show_queue(callback, user_id)
    elif action == "add":
        await enter_add_mode(callback, user_id)
    elif action == "refresh":
        await refresh_main(callback, user_id)
    elif action == "help":
        await show_help(callback)
    else:
        await callback.answer("Unknown action", show_alert=True)


async def start_radio(callback: CallbackQuery, user_id: int, username: str):
    """Start a new radio session."""
    # Check if already has session
    existing = get_player(str(user_id))
    if existing:
        await callback.answer("You already have an active radio!", show_alert=True)
        return
    
    # Create player
    player = create_player(str(user_id), user_id)
    player.owner_username = username
    
    # Start the player (will play fallback if no tracks)
    await player.start()
    
    stream_url = config.get_stream_url(str(user_id))
    
    text = f"""
✅ **Your Radio is LIVE!**

🔗 **Stream URL:**
`{stream_url}`

📡 **How to listen:**
1. Open VLC Media Player
2. Go to Media → Open Network Stream
3. Paste the URL above
4. Click Play!

🎵 Add songs using the button below.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=radio_controls_keyboard(is_paused=False)
    )
    await callback.answer("Radio started! 🎵")


async def confirm_stop(callback: CallbackQuery):
    """Show stop confirmation."""
    await callback.message.edit_text(
        "⚠️ **Stop Radio?**\n\nThis will disconnect all listeners.",
        reply_markup=confirm_stop_keyboard()
    )


async def stop_radio(callback: CallbackQuery, user_id: int):
    """Stop the radio session."""
    player = get_player(str(user_id))
    if player:
        await player.stop()
        remove_player(str(user_id))
        remove_queue(str(user_id))
    
    await callback.message.edit_text(
        "🛑 **Radio Stopped**\n\nThanks for streaming!",
        reply_markup=main_menu_keyboard(has_session=False)
    )
    await callback.answer("Radio stopped")


async def skip_track(callback: CallbackQuery, user_id: int):
    """Skip current track."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    await player.skip()
    await callback.answer("⏭️ Skipped!")
    await show_status(callback, user_id)


async def pause_radio(callback: CallbackQuery, user_id: int):
    """Pause the radio."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    await player.pause()
    await callback.message.edit_reply_markup(
        reply_markup=radio_controls_keyboard(is_paused=True)
    )
    await callback.answer("⏸️ Paused")


async def resume_radio(callback: CallbackQuery, user_id: int):
    """Resume the radio."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    await player.resume()
    await callback.message.edit_reply_markup(
        reply_markup=radio_controls_keyboard(is_paused=False)
    )
    await callback.answer("▶️ Resumed")


async def show_status(callback: CallbackQuery, user_id: int):
    """Show current status."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    status = player.get_status()
    current_title = status.get("current_title", "Nothing playing")
    listeners = status.get("listener_count", 0)
    pending = status.get("pending_tracks", 0)
    state = status.get("state", "unknown")
    stream_url = status.get("stream_url", "")
    
    state_emoji = "▶️" if state == "playing" else "⏸️" if state == "paused" else "⏳"
    
    text = f"""
📊 **Radio Status**

{state_emoji} **Now Playing:**
🎵 {current_title}

🎧 **Listeners:** {listeners}
📋 **Queue:** {pending} tracks

🔗 `{stream_url}`
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=radio_controls_keyboard(is_paused=(state == "paused"))
    )
    await callback.answer()


async def show_listeners(callback: CallbackQuery, user_id: int):
    """Show listener count."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    count = player.listener_count
    await callback.answer(f"🎧 {count} listener(s) connected", show_alert=True)


async def show_queue(callback: CallbackQuery, user_id: int):
    """Show queue."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    queue = player.queue
    items = queue.get_pending_tracks()
    current = queue.get_current()
    
    if not items and not current:
        text = "📋 **Queue Empty**\n\nAdd tracks using the ➕ Add button!"
    else:
        text = "📋 **Queue**\n\n"
        if current:
            text += f"▶️ **Now:** {current.track.title}\n\n"
        
        if items:
            text += "**Up Next:**\n"
            for i, item in enumerate(items[:5]):
                text += f"{item.position}. {item.track.title}\n"
            
            if len(items) > 5:
                text += f"\n_...and {len(items) - 5} more_"
    
    # Build queue items for keyboard
    queue_items = [{"title": item.track.title, "position": item.position} for item in items]
    
    await callback.message.edit_text(
        text,
        reply_markup=queue_keyboard(queue_items) if queue_items else back_keyboard()
    )
    await callback.answer()


async def enter_add_mode(callback: CallbackQuery, user_id: int):
    """Enter add track mode."""
    player = get_player(str(user_id))
    if not player:
        await callback.answer("No active radio session", show_alert=True)
        return
    
    _user_add_mode[user_id] = True
    
    text = """
➕ **Add Tracks**

Send me:
• A Spotify track link
• A Spotify album link
• A Spotify playlist link
• Or just type a song name to search!
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=add_mode_keyboard()
    )
    await callback.answer()


async def refresh_main(callback: CallbackQuery, user_id: int):
    """Refresh main screen."""
    _user_add_mode.pop(user_id, None)  # Exit add mode
    
    player = get_player(str(user_id))
    has_session = player is not None
    
    if has_session:
        await show_status(callback, user_id)
    else:
        text = """
🎵 **Z Stream Radio**

Click **📻 Start Radio** to begin streaming.
"""
        await callback.message.edit_text(
            text,
            reply_markup=main_menu_keyboard(has_session=False)
        )
    await callback.answer()


async def show_help(callback: CallbackQuery):
    """Show help text."""
    text = """
❓ **Help**

**How it works:**
1. Start your radio session
2. Copy the stream URL
3. Open VLC and paste the URL
4. Add songs via Spotify links or search

**Adding Songs:**
• Send Spotify track/album/playlist links
• Use the Search button

**Tips:**
• Multiple people can listen
• Queue keeps the music going!
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(has_session=False)
    )
    await callback.answer()


def is_in_add_mode(user_id: int) -> bool:
    """Check if user is in add mode."""
    return _user_add_mode.get(user_id, False)


def exit_add_mode(user_id: int):
    """Exit add mode for user."""
    _user_add_mode.pop(user_id, None)
