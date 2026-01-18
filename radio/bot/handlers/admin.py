"""
Radio Bot - Admin Handlers

Admin dashboard and management callbacks.
"""

import logging
import psutil
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from bot.keyboards import (
    admin_dashboard_keyboard,
    admin_sessions_keyboard,
    admin_confirm_kick_keyboard,
    admin_confirm_stopall_keyboard,
    back_keyboard
)
from bot.client import is_admin
from core.player import get_player, get_all_players, remove_player
from core.queue_manager import remove_queue
import config

logger = logging.getLogger(__name__)


async def admin_command(client: Client, message: Message):
    """Handle /admin command."""
    user = message.from_user
    user_id = user.id
    
    if not is_admin(user_id):
        await message.reply("⛔ You don't have admin access.", quote=True)
        return
    
    await show_admin_dashboard(message=message)


async def handle_admin_callback(client: Client, callback: CallbackQuery):
    """Handle admin:* callbacks."""
    user = callback.from_user
    user_id = user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Admin access required", show_alert=True)
        return
    
    data = callback.data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    
    logger.info(f"Admin callback: {data} from {user_id}")
    
    if action == "refresh":
        await show_admin_dashboard(callback=callback)
    elif action == "sessions":
        await show_sessions(callback)
    elif action == "stats":
        await show_stats(callback)
    elif action == "view":
        session_id = parts[2] if len(parts) > 2 else ""
        await view_session(callback, session_id)
    elif action == "kick":
        if len(parts) > 2 and parts[2] == "confirm":
            session_id = parts[3] if len(parts) > 3 else ""
            await kick_session_confirm(callback, session_id)
        else:
            session_id = parts[2] if len(parts) > 2 else ""
            await kick_session_prompt(callback, session_id)
    elif action == "stopall":
        if len(parts) > 2 and parts[2] == "confirm":
            await stop_all_sessions(callback)
        else:
            await stop_all_prompt(callback)
    else:
        await callback.answer("Unknown admin action", show_alert=True)


async def show_admin_dashboard(message: Message = None, callback: CallbackQuery = None):
    """Show admin dashboard."""
    players = get_all_players()
    total_listeners = sum(p.listener_count for p in players)
    
    # Get system stats
    try:
        memory = psutil.virtual_memory()
        mem_used = f"{memory.used // (1024*1024)}MB"
        mem_total = f"{memory.total // (1024*1024)}MB"
        mem_percent = f"{memory.percent}%"
    except:
        mem_used = "N/A"
        mem_total = "N/A"
        mem_percent = "N/A"
    
    text = f"""
📻 **RADIO ADMIN DASHBOARD**
━━━━━━━━━━━━━━━━━━━━━━━━

📊 **Server Stats**
├─ Active Sessions: {len(players)}/{config.MAX_SESSIONS}
├─ Total Listeners: {total_listeners}
└─ Memory: {mem_used}/{mem_total} ({mem_percent})

"""
    
    if players:
        text += "🎵 **Active Sessions:**\n"
        for p in players[:5]:
            state = "▶️" if p.state.value == "playing" else "⏸️"
            text += f"├─ {state} @{p.owner_username or 'Unknown'} ({p.listener_count}🎧)\n"
        if len(players) > 5:
            text += f"└─ _...and {len(players) - 5} more_\n"
    else:
        text += "📭 No active sessions\n"
    
    if message:
        await message.reply(text, reply_markup=admin_dashboard_keyboard(), quote=True)
    elif callback:
        await callback.message.edit_text(text, reply_markup=admin_dashboard_keyboard())
        await callback.answer()


async def show_sessions(callback: CallbackQuery):
    """Show all active sessions."""
    players = get_all_players()
    
    if not players:
        await callback.answer("No active sessions", show_alert=True)
        return
    
    text = f"📋 **Active Sessions** ({len(players)}/{config.MAX_SESSIONS})\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Click to view details or kick:\n"
    
    sessions = [p.get_status() for p in players]
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_sessions_keyboard(sessions)
    )
    await callback.answer()


async def show_stats(callback: CallbackQuery):
    """Show server statistics."""
    players = get_all_players()
    total_listeners = sum(p.listener_count for p in players)
    
    try:
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage('/')
        
        text = f"""
📊 **Server Statistics**
━━━━━━━━━━━━━━━━━━━━━━━━

**Sessions**
├─ Active: {len(players)}/{config.MAX_SESSIONS}
└─ Listeners: {total_listeners}

**System**
├─ CPU: {cpu}%
├─ RAM: {memory.used // (1024*1024)}MB / {memory.total // (1024*1024)}MB ({memory.percent}%)
└─ Disk: {disk.used // (1024*1024*1024)}GB / {disk.total // (1024*1024*1024)}GB ({disk.percent}%)

**Config**
├─ Port: {config.RADIO_PORT}
├─ Bitrate: {config.AUDIO_BITRATE}kbps
└─ Timeout: {config.SESSION_TIMEOUT_MINUTES}min
"""
    except Exception as e:
        text = f"📊 **Stats Error:** {e}"
    
    await callback.message.edit_text(text, reply_markup=admin_dashboard_keyboard())
    await callback.answer()


async def view_session(callback: CallbackQuery, session_id: str):
    """View details of a specific session."""
    player = get_player(session_id)
    if not player:
        await callback.answer("Session not found", show_alert=True)
        return
    
    status = player.get_status()
    queue = player.queue.to_dict()
    
    text = f"""
👁️ **Session Details**
━━━━━━━━━━━━━━━━━━━━━━━━

**Owner:** @{status.get('owner_username', 'Unknown')}
**Session ID:** `{session_id}`
**State:** {status.get('state', 'unknown')}

**Now Playing:**
🎵 {status.get('current_title', 'Nothing')}

**Stats:**
├─ Listeners: {status.get('listener_count', 0)}
├─ Queue: {queue.get('pending_count', 0)} pending
└─ URL: `{status.get('stream_url', 'N/A')}`
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_confirm_kick_keyboard(session_id)
    )
    await callback.answer()


async def kick_session_prompt(callback: CallbackQuery, session_id: str):
    """Show kick confirmation."""
    player = get_player(session_id)
    if not player:
        await callback.answer("Session not found", show_alert=True)
        return
    
    text = f"""
⚠️ **Kick Session?**

Owner: @{player.owner_username or 'Unknown'}
Listeners: {player.listener_count}

This will stop the session and disconnect all listeners.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_confirm_kick_keyboard(session_id)
    )
    await callback.answer()


async def kick_session_confirm(callback: CallbackQuery, session_id: str):
    """Actually kick a session."""
    player = get_player(session_id)
    if player:
        await player.stop()
        remove_player(session_id)
        remove_queue(session_id)
        await callback.answer(f"✅ Session {session_id} kicked", show_alert=True)
    else:
        await callback.answer("Session already stopped", show_alert=True)
    
    await show_sessions(callback)


async def stop_all_prompt(callback: CallbackQuery):
    """Show stop all confirmation."""
    players = get_all_players()
    total_listeners = sum(p.listener_count for p in players)
    
    text = f"""
⚠️ **Stop ALL Sessions?**

This will stop {len(players)} session(s) and disconnect {total_listeners} listener(s).

Are you sure?
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=admin_confirm_stopall_keyboard()
    )
    await callback.answer()


async def stop_all_sessions(callback: CallbackQuery):
    """Stop all sessions."""
    players = get_all_players()
    count = len(players)
    
    for player in players:
        await player.stop()
        remove_player(player.session_id)
        remove_queue(player.session_id)
    
    await callback.answer(f"✅ Stopped {count} sessions", show_alert=True)
    await show_admin_dashboard(callback=callback)
