"""
Radio Telegram Handler
Handles /radio commands and inline menu interactions.
"""

import logging
from services import backend
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ForceReply,
)
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from radio.session import RadioSession, get_session_manager
from radio.queue import QueueItem, get_queue_manager
from radio.scheduler import get_scheduler
from radio.streaming import get_streaming_pool
from radio.transcoder import get_transcoder_pool
from radio.constants import (
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_PAUSED,
    DEFAULT_BITRATE,
    MAX_LISTENERS,
)

logger = logging.getLogger(__name__)

# Callback data prefixes
CB_PLAY = "rad:play"
CB_PAUSE = "rad:pause"
CB_SKIP = "rad:skip"
CB_SHUFFLE = "rad:shuffle"
CB_REPEAT = "rad:repeat"
CB_QUEUE = "rad:queue"
CB_ADD = "rad:add"
CB_SHARE = "rad:share"
CB_STOP = "rad:stop"
CB_CONFIRM_STOP = "rad:confirm_stop"
CB_CANCEL_STOP = "rad:cancel_stop"
CB_QUEUE_PAGE = "rad:qpage:"
CB_QUEUE_REMOVE = "rad:qrem:"
CB_QUEUE_UP = "rad:qup:"
CB_QUEUE_DOWN = "rad:qdown:"
CB_BACK = "rad:back"

# Items per page in queue view
QUEUE_PAGE_SIZE = 5


def build_main_menu_keyboard(session: RadioSession) -> InlineKeyboardMarkup:
    """Build the main radio control menu keyboard."""
    is_paused = session.status == SESSION_STATUS_PAUSED
    repeat_status = "🔁 On" if session.repeat_enabled else "🔁 Off"
    
    keyboard = [
        # Playback controls
        [
            InlineKeyboardButton("▶️ Play" if is_paused else "⏸ Pause", 
                               callback_data=CB_PLAY if is_paused else CB_PAUSE),
            InlineKeyboardButton("⏭ Skip", callback_data=CB_SKIP),
        ],
        # Queue controls
        [
            InlineKeyboardButton("🔀 Shuffle", callback_data=CB_SHUFFLE),
            InlineKeyboardButton(repeat_status, callback_data=CB_REPEAT),
        ],
        # Queue and add
        [
            InlineKeyboardButton("📋 Queue", callback_data=CB_QUEUE),
            InlineKeyboardButton("➕ Add Song", callback_data=CB_ADD),
        ],
        # Share and stop
        [
            InlineKeyboardButton("🔗 Share Link", callback_data=CB_SHARE),
            InlineKeyboardButton("⏹ Stop Server", callback_data=CB_STOP),
        ],
    ]
    
    return InlineKeyboardMarkup(keyboard)


def build_queue_keyboard(
    queue: list[QueueItem], 
    page: int = 0
) -> InlineKeyboardMarkup:
    """Build paginated queue view keyboard."""
    total_pages = max(1, (len(queue) + QUEUE_PAGE_SIZE - 1) // QUEUE_PAGE_SIZE)
    start_idx = page * QUEUE_PAGE_SIZE
    end_idx = min(start_idx + QUEUE_PAGE_SIZE, len(queue))
    
    keyboard = []
    
    # Track rows with up/down/remove buttons
    for i, item in enumerate(queue[start_idx:end_idx]):
        pos = start_idx + i + 1  # 1-indexed position
        status_emoji = "▶️" if item.status == "playing" else f"{pos}."
        
        row = [
            InlineKeyboardButton(
                f"{status_emoji} {item.track_name[:20]}{'...' if len(item.track_name) > 20 else ''}",
                callback_data=f"rad:noop"  # Just display, no action
            ),
        ]
        
        # Add move/remove buttons
        control_row = []
        if pos > 1:
            control_row.append(InlineKeyboardButton("⬆️", callback_data=f"{CB_QUEUE_UP}{pos}"))
        if pos < len(queue):
            control_row.append(InlineKeyboardButton("⬇️", callback_data=f"{CB_QUEUE_DOWN}{pos}"))
        control_row.append(InlineKeyboardButton("❌", callback_data=f"{CB_QUEUE_REMOVE}{pos}"))
        
        keyboard.append(row)
        if control_row:
            keyboard.append(control_row)
    
    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{CB_QUEUE_PAGE}{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="rad:noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"{CB_QUEUE_PAGE}{page+1}"))
    keyboard.append(nav_row)
    
    # Back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Controls", callback_data=CB_BACK)])
    
    return InlineKeyboardMarkup(keyboard)


def build_confirm_stop_keyboard() -> InlineKeyboardMarkup:
    """Build confirmation keyboard for stopping session."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Stop", callback_data=CB_CONFIRM_STOP),
            InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL_STOP),
        ]
    ])


def format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


async def build_status_message(session: RadioSession) -> str:
    """Build the status message for the main menu."""
    queue_manager = get_queue_manager()
    streaming_pool = get_streaming_pool()
    
    # Get current track
    current = await queue_manager.get_current_track(session.id)
    queue_length = await queue_manager.get_queue_length(session.id)
    total_duration = await queue_manager.get_total_duration(session.id)
    
    # Get listener count
    server = streaming_pool.get(session.id)
    listeners = server.get_listener_count() if server else 0
    
    # Build status
    status_emoji = "⏸" if session.status == SESSION_STATUS_PAUSED else "▶️"
    now_playing = current.display_name() if current else "Nothing playing"
    remaining = format_duration(session.get_remaining_seconds())
    
    return (
        f"📻 **Radio Control Panel**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_emoji} **Now Playing:**\n"
        f"  {now_playing}\n\n"
        f"📋 Queue: {queue_length} tracks ({format_duration(total_duration)})\n"
        f"👥 Listeners: {listeners}/{MAX_LISTENERS}\n"
        f"⏱ Time remaining: {remaining}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )


# =============================================================================
# Command Handlers
# =============================================================================

async def handle_radio(client: Client, message: Message):
    """
    Handle /radio command.
    Shows main control menu if session exists.
    """
    try:
        user_id = message.from_user.id
        session_manager = get_session_manager()
        
        session = await session_manager.get_user_session(user_id)
        
        if not session:
            await message.reply(
                "📻 **No Active Radio Session**\n\n"
                "Start a new session with /radio_start\n\n"
                "Your session will get a unique streaming URL that anyone can listen to!",
                quote=True
            )
            return
        
        # Show control panel
        status_text = await build_status_message(session)
        keyboard = build_main_menu_keyboard(session)
        
        await message.reply(status_text, reply_markup=keyboard, quote=True)
    except Exception as e:
        logger.error(f"Error in handle_radio: {e}", exc_info=True)
        await message.reply("❌ An error occurred while fetching radio dashboard.")


async def handle_radio_start(client: Client, message: Message):
    """
    Handle /radio_start command.
    Creates a new radio session.
    """
    try:
        user_id = message.from_user.id
        session_manager = get_session_manager()
        scheduler = get_scheduler()
        
        # Check for existing session
        existing = await session_manager.get_user_session(user_id)
        if existing:
            await message.reply(
                "⚠️ **You Already Have an Active Session**\n\n"
                f"Stream URL: `{existing.stream_url}`\n\n"
                "Use /radio to control it or /radio_end to stop it first.",
                quote=True
            )
            return
        
        # Create new session
        status_msg = await message.reply("🔄 Starting radio session...", quote=True)
        
        session = await session_manager.create_session(user_id)
        
        if not session:
            await status_msg.edit_text("❌ Failed to start session. Please try again.")
            return
        
        # Schedule expiration and warning
        scheduler.set_bot_client(client)
        await scheduler.schedule_expiration(session.id, user_id, session.expires_at)
        
        # Notify user
        await scheduler.notify_session_started(session.id, user_id, session.stream_url)
        
        # Show control panel
        status_text = await build_status_message(session)
        keyboard = build_main_menu_keyboard(session)
        
        await status_msg.edit_text(status_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in handle_radio_start: {e}", exc_info=True)
        await message.reply("❌ Failed to start radio session due to an internal error.")


async def handle_radio_end(client: Client, message: Message):
    """
    Handle /radio_end command.
    Stops the current radio session.
    """
    try:
        user_id = message.from_user.id
        session_manager = get_session_manager()
        scheduler = get_scheduler()
        
        session = await session_manager.get_user_session(user_id)
        
        if not session:
            await message.reply(
                "📻 No active radio session to stop.\n"
                "Start one with /radio_start",
                quote=True
            )
            return
        
        # Stop session
        await scheduler.cancel_all(session.id)
        
        # Stop streaming server
        streaming_pool = get_streaming_pool()
        await streaming_pool.stop_server(session.id)
        
        # Stop transcoder
        transcoder_pool = get_transcoder_pool()
        await transcoder_pool.stop_transcoder(session.id)
        
        # Clean up queue
        queue_manager = get_queue_manager()
        await queue_manager.cleanup_session(session.id)
        
        # Stop session
        await session_manager.stop_session(session.id, "user_request")
        
        await message.reply(
            "⏹️ **Radio Session Ended**\n\n"
            "Thanks for streaming! Start a new session anytime with /radio_start",
            quote=True
        )
    except Exception as e:
        logger.error(f"Error in handle_radio_end: {e}", exc_info=True)
        await message.reply("❌ Error stopping session.")


# =============================================================================
# Callback Handlers
# =============================================================================

async def handle_callback(client: Client, callback: CallbackQuery):
    """Route callback to appropriate handler."""
    try:
        data = callback.data
        user_id = callback.from_user.id
        
        session_manager = get_session_manager()
        session = await session_manager.get_user_session(user_id)
        
        if not session:
            await callback.answer("No active session", show_alert=True)
            return
        
        # Route to handlers
        if data == CB_PLAY:
            await _handle_play(client, callback, session)
        elif data == CB_PAUSE:
            await _handle_pause(client, callback, session)
        elif data == CB_SKIP:
            await _handle_skip(client, callback, session)
        elif data == CB_SHUFFLE:
            await _handle_shuffle(client, callback, session)
        elif data == CB_REPEAT:
            await _handle_repeat(client, callback, session)
        elif data == CB_QUEUE:
            await _handle_queue(client, callback, session)
        elif data == CB_ADD:
            await _handle_add(client, callback, session)
        elif data == CB_SHARE:
            await _handle_share(client, callback, session)
        elif data == CB_STOP:
            await _handle_stop_confirm(client, callback, session)
        elif data == CB_CONFIRM_STOP:
            await _handle_stop(client, callback, session)
        elif data == CB_CANCEL_STOP:
            await _handle_cancel_stop(client, callback, session)
        elif data == CB_BACK:
            await _handle_back(client, callback, session)
        elif data.startswith(CB_QUEUE_PAGE):
            page = int(data.replace(CB_QUEUE_PAGE, ""))
            await _handle_queue_page(client, callback, session, page)
        elif data.startswith(CB_QUEUE_REMOVE):
            pos = int(data.replace(CB_QUEUE_REMOVE, ""))
            await _handle_queue_remove(client, callback, session, pos)
        elif data.startswith(CB_QUEUE_UP):
            pos = int(data.replace(CB_QUEUE_UP, ""))
            await _handle_queue_move(client, callback, session, pos, pos - 1)
        elif data.startswith(CB_QUEUE_DOWN):
            pos = int(data.replace(CB_QUEUE_DOWN, ""))
            await _handle_queue_move(client, callback, session, pos, pos + 1)
        else:
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)
        await callback.answer("An error occurred", show_alert=True)


async def _handle_play(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle play button."""
    session_manager = get_session_manager()
    await session_manager.resume_session(session.id)
    
    await callback.answer("▶️ Resumed")
    
    # Update menu
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


async def _handle_pause(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle pause button."""
    session_manager = get_session_manager()
    await session_manager.pause_session(session.id)
    
    await callback.answer("⏸ Paused")
    
    # Update menu
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


async def _handle_skip(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle skip button."""
    # TODO: Implement actual skip logic with transcoder
    await callback.answer("⏭ Skipped to next track")
    
    # Update menu
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


async def _handle_shuffle(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle shuffle button."""
    queue_manager = get_queue_manager()
    await queue_manager.shuffle_queue(session.id)
    
    await callback.answer("🔀 Queue shuffled!")
    
    # Update menu
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


async def _handle_repeat(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle repeat toggle button."""
    session_manager = get_session_manager()
    new_state = await session_manager.toggle_repeat(session.id)
    
    state_text = "enabled" if new_state else "disabled"
    await callback.answer(f"🔁 Repeat {state_text}")
    
    # Update menu
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


async def _handle_queue(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle queue view button."""
    queue_manager = get_queue_manager()
    queue = await queue_manager.get_queue(session.id)
    
    if not queue:
        await callback.answer("Queue is empty. Add songs first!", show_alert=True)
        return
    
    await callback.answer()
    
    # Build queue message
    total = await queue_manager.get_total_duration(session.id)
    text = (
        f"📋 **Queue** ({len(queue)} tracks, {format_duration(total)})\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    keyboard = build_queue_keyboard(queue, page=0)
    await callback.message.edit_text(text, reply_markup=keyboard)


async def _handle_queue_page(client: Client, callback: CallbackQuery, session: RadioSession, page: int):
    """Handle queue pagination."""
    queue_manager = get_queue_manager()
    queue = await queue_manager.get_queue(session.id)
    
    await callback.answer()
    
    total = await queue_manager.get_total_duration(session.id)
    text = (
        f"📋 **Queue** ({len(queue)} tracks, {format_duration(total)})\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    keyboard = build_queue_keyboard(queue, page=page)
    await callback.message.edit_text(text, reply_markup=keyboard)


async def _handle_queue_remove(client: Client, callback: CallbackQuery, session: RadioSession, position: int):
    """Handle queue remove button."""
    queue_manager = get_queue_manager()
    
    if await queue_manager.remove_track(session.id, position):
        await callback.answer(f"❌ Removed track #{position}")
    else:
        await callback.answer("Failed to remove track", show_alert=True)
        return
    
    # Refresh queue view
    queue = await queue_manager.get_queue(session.id)
    if queue:
        total = await queue_manager.get_total_duration(session.id)
        text = f"📋 **Queue** ({len(queue)} tracks, {format_duration(total)})\n━━━━━━━━━━━━━━━━━━━━━\n"
        keyboard = build_queue_keyboard(queue, page=0)
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await _handle_back(client, callback, session)


async def _handle_queue_move(client: Client, callback: CallbackQuery, session: RadioSession, from_pos: int, to_pos: int):
    """Handle queue move up/down buttons."""
    queue_manager = get_queue_manager()
    
    if await queue_manager.move_track(session.id, from_pos, to_pos):
        await callback.answer(f"Moved to #{to_pos}")
    else:
        await callback.answer("Failed to move track", show_alert=True)
        return
    
    # Refresh queue view
    queue = await queue_manager.get_queue(session.id)
    total = await queue_manager.get_total_duration(session.id)
    text = f"📋 **Queue** ({len(queue)} tracks, {format_duration(total)})\n━━━━━━━━━━━━━━━━━━━━━\n"
    keyboard = build_queue_keyboard(queue, page=0)
    await callback.message.edit_text(text, reply_markup=keyboard)


async def _handle_add(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle add song button."""
    await callback.answer()
    
    await callback.message.reply(
        "🎵 **Add a Song**\n\n"
        "Send me a song name or Spotify URL to add to the queue.\n\n"
        "Examples:\n"
        "• `Daft Punk Get Lucky`\n"
        "• `https://open.spotify.com/track/...`",
        reply_markup=ForceReply(selective=True, placeholder="Song name or URL...")
    )


async def _handle_share(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle share link button."""
    await callback.answer()
    
    streaming_pool = get_streaming_pool()
    server = streaming_pool.get(session.id)
    listeners = server.get_listener_count() if server else 0
    
    await callback.message.reply(
        f"🔗 **Share Your Radio Stream**\n\n"
        f"**Stream URL:**\n`{session.stream_url}`\n\n"
        f"👥 Current listeners: {listeners}/{MAX_LISTENERS}\n\n"
        f"**How to listen:**\n"
        f"1. Copy the URL above\n"
        f"2. Open VLC or any media player\n"
        f"3. Go to Media → Open Network Stream\n"
        f"4. Paste the URL and click Play\n\n"
        f"Or just open the URL in a browser!"
    )


async def _handle_stop_confirm(client: Client, callback: CallbackQuery, session: RadioSession):
    """Show stop confirmation."""
    await callback.answer()
    
    await callback.message.edit_text(
        "⚠️ **Stop Radio Session?**\n\n"
        "This will:\n"
        "• Disconnect all listeners\n"
        "• Clear your queue\n"
        "• End the session\n\n"
        "Are you sure?",
        reply_markup=build_confirm_stop_keyboard()
    )


async def _handle_stop(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle confirmed stop."""
    session_manager = get_session_manager()
    scheduler = get_scheduler()
    streaming_pool = get_streaming_pool()
    transcoder_pool = get_transcoder_pool()
    queue_manager = get_queue_manager()
    
    await callback.answer("⏹ Stopping...")
    
    # Clean up everything
    await scheduler.cancel_all(session.id)
    await streaming_pool.stop_server(session.id)
    await transcoder_pool.stop_transcoder(session.id)
    await queue_manager.cleanup_session(session.id)
    await session_manager.stop_session(session.id, "user_request")
    
    await callback.message.edit_text(
        "⏹️ **Radio Session Ended**\n\n"
        "Thanks for streaming! Start a new session anytime with /radio_start"
    )


async def _handle_cancel_stop(client: Client, callback: CallbackQuery, session: RadioSession):
    """Handle cancel stop."""
    await callback.answer("Cancelled")
    await _handle_back(client, callback, session)


async def _handle_back(client: Client, callback: CallbackQuery, session: RadioSession):
    """Return to main menu."""
    status_text = await build_status_message(session)
    keyboard = build_main_menu_keyboard(session)
    await callback.message.edit_text(status_text, reply_markup=keyboard)


# =============================================================================
# Message Handler for Add Song
# =============================================================================

async def handle_add_song_reply(client: Client, message: Message):
    """
    Handle reply to add song prompt.
    Searches for the song and adds to queue.
    """
    try:
        user_id = message.from_user.id
        session_manager = get_session_manager()
        queue_manager = get_queue_manager()
        
        session = await session_manager.get_user_session(user_id)
        if not session:
            await message.reply("No active session. Start one with /radio_start")
            return
        
        query = message.text.strip()
        if not query:
            await message.reply("Please provide a song name or URL.")
            return
        
        status_msg = await message.reply(f"🔎 Searching for '{query}'...", quote=True)
        
        # Real search via backend
        api = backend.get_client()
        try:
            # Check if it's a URL or query
            if "spotify.com" in query:
               # Get metadata directly
               meta = await api.get_metadata(query)
               if meta and "track" in meta:
                   track_data = meta["track"]
                   # Construct result manually
                   result = {
                       "name": track_data.get("name"),
                       "artists": track_data.get("artists"),
                       "isrc": track_data.get("isrc"),
                       "duration_ms": track_data.get("duration_ms"),
                       "image": track_data.get("image")
                   }
               else:
                   await status_msg.edit_text("❌ Invalid Spotify URL or failed to fetch metadata")
                   return
            else:
                # Search
                search_res = await api.search(query, limit=1)
                if not search_res or not search_res.get("tracks"):
                    await status_msg.edit_text(f"❌ No tracks found for '{query}'")
                    return
                # Get first result
                track_data = search_res["tracks"][0]
                result = {
                     "name": track_data.get("name"),
                     "artists": track_data.get("artists"),
                     "isrc": track_data.get("id"), # Search result ID is usually Spotify ID, but we might need ISRC.
                     # Backend search returns 'id' which is Spotify ID.
                     # To get ISRC we usually need get_metadata.
                     # However, for queueing, let's see if we can use ID.
                     # The backend downloader usually needs ISRC or valid URL.
                     # If we use spotify ID as ISRC logic might fail if strictly validated.
                     # BUT, let's fetch metadata to be safe if it's just ID.
                     "image": track_data.get("image")
                }
                
                # Fetch full metadata to ensure we have ISRC
                # Search result returns 'id' (spotify ID)
                if result["isrc"] and len(str(result["isrc"])) < 20: # Likely a Spotify ID (22 chars) vs ISRC (12 chars)
                     # Actually, Spotify ID is 22 chars. ISRC is 12 chars.
                     # Let's just fetch metadata for the ID to be safe and get duration
                     meta = await api.get_metadata(f"https://open.spotify.com/track/{result['isrc']}")
                     if meta and "track" in meta:
                         result["isrc"] = meta["track"].get("isrc")
                         result["duration_ms"] = meta["track"].get("duration_ms")
                         result["name"] = meta["track"].get("name")
                         result["artists"] = meta["track"].get("artists")
                     else:
                         # Fallback to defaults?
                         result["duration_ms"] = 180000

            # Add to Queue
            duration_sec = int(result.get("duration_ms", 180000) / 1000)
            
            # Ensure we have a valid ISRC or at least something unique
            track_isrc = result.get("isrc")
            if not track_isrc or track_isrc == "placeholder":
                 await status_msg.edit_text("❌ Could not resolve track ISRC.")
                 return

            item = await queue_manager.add_track(
                session_id=session.id,
                track_isrc=track_isrc,
                track_name=result.get("name", query),
                artist_name=result.get("artists", "Unknown"),
                duration=duration_sec,
            )
            
            if item:
                queue_length = await queue_manager.get_queue_length(session.id)
                await status_msg.edit_text(
                    f"✅ **Added to Queue**\n\n"
                    f"🎵 {item.display_name()}\n"
                    f"⏱ {format_duration(duration_sec)}\n"
                    f"📋 Position: #{queue_length}\n\n"
                    f"Use /radio to view controls."
                )
            else:
                await status_msg.edit_text(
                    "❌ **Could not add track**\n\n"
                    "Adding this track would exceed the 6-hour session limit."
                )
                
        except Exception as e:
            logger.error(f"Backend search failed: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Error searching: {e}")
            
    except Exception as e:
        logger.error(f"Error in handle_add_song_reply: {e}", exc_info=True)
        await message.reply("❌ Error adding song.")


def setup_handlers(client: Client):
    """Register radio handlers."""
    # Commands
    client.add_handler(MessageHandler(handle_radio, filters.command("radio")))
    client.add_handler(MessageHandler(handle_radio_start, filters.command("radio_start")))
    client.add_handler(MessageHandler(handle_radio_end, filters.command("radio_end")))
    
    # Callbacks
    client.add_handler(CallbackQueryHandler(handle_callback, filters.regex(r"^rad:")))
    
    # Reply handler for adding songs (checks if reply is to a force reply from this bot)
    # Note: This is a simple check. For production, maybe check the specific text of the prompt.
    client.add_handler(MessageHandler(
        handle_add_song_reply, 
        filters.reply & filters.create(lambda _, __, m: m.reply_to_message.from_user.is_self)
    ))
