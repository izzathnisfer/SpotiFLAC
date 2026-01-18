"""
Radio Bot - Inline Keyboard Builders
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard(has_session: bool = False) -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    if has_session:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Track", callback_data="radio:add"),
                InlineKeyboardButton("📋 Queue", callback_data="radio:queue"),
            ],
            [
                InlineKeyboardButton("⏭️ Skip", callback_data="radio:skip"),
                InlineKeyboardButton("⏸️ Pause", callback_data="radio:pause"),
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data="radio:status"),
                InlineKeyboardButton("👥 Listeners", callback_data="radio:listeners"),
            ],
            [
                InlineKeyboardButton("🛑 Stop Radio", callback_data="radio:stop"),
            ],
        ])
    else:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📻 Start Radio", callback_data="radio:start"),
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="radio:help"),
            ],
        ])


def radio_controls_keyboard(is_paused: bool = False) -> InlineKeyboardMarkup:
    """Radio control buttons."""
    pause_btn = InlineKeyboardButton("▶️ Resume", callback_data="radio:resume") if is_paused else \
                InlineKeyboardButton("⏸️ Pause", callback_data="radio:pause")
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add", callback_data="radio:add"),
            InlineKeyboardButton("📋 Queue", callback_data="radio:queue"),
        ],
        [
            InlineKeyboardButton("⏭️ Skip", callback_data="radio:skip"),
            pause_btn,
        ],
        [
            InlineKeyboardButton("📊 Status", callback_data="radio:status"),
            InlineKeyboardButton("🔄 Refresh", callback_data="radio:refresh"),
        ],
        [
            InlineKeyboardButton("🛑 Stop Radio", callback_data="radio:stop"),
        ],
    ])


def confirm_stop_keyboard() -> InlineKeyboardMarkup:
    """Confirmation for stopping radio."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Stop", callback_data="radio:stop:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="radio:refresh"),
        ],
    ])


def add_mode_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown when in add track mode."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Spotify", callback_data="radio:search"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="radio:refresh"),
        ],
    ])


def search_results_keyboard(results: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Keyboard for search results with pagination. Uses numeric indices."""
    buttons = []
    
    # Add track buttons (max 10)
    for i, track in enumerate(results[:10]):
        source = track.get("source", "spotify")
        icon = "🎵" if source == "spotify" else "📺"
        title = track.get("name", "Unknown")[:25]
        artist = track.get("artists", "Unknown")[:15]
        buttons.append([
            InlineKeyboardButton(
                f"{icon} {title} - {artist}",
                callback_data=f"search:add:{i}"
            )
        ])
    
    # Cancel button
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="radio:refresh")])
    
    return InlineKeyboardMarkup(buttons)


def queue_keyboard(queue_items: list) -> InlineKeyboardMarkup:
    """Keyboard for queue view with remove options."""
    buttons = []
    
    # Show pending tracks (max 5)
    for i, item in enumerate(queue_items[:5]):
        title = item.get("title", "Unknown")[:25]
        position = item.get("position", i+1)
        buttons.append([
            InlineKeyboardButton(
                f"🗑️ {position}. {title}",
                callback_data=f"queue:remove:{position}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton("🗑️ Clear Queue", callback_data="queue:clear"),
    ])
    buttons.append([
        InlineKeyboardButton("◀️ Back", callback_data="radio:refresh"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def back_keyboard() -> InlineKeyboardMarkup:
    """Simple back button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back", callback_data="radio:refresh")],
    ])


# ============================================
# Admin Keyboards
# ============================================

def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard main menu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Sessions", callback_data="admin:sessions"),
            InlineKeyboardButton("📊 Stats", callback_data="admin:stats"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="admin:refresh"),
        ],
        [
            InlineKeyboardButton("⚠️ Stop All", callback_data="admin:stopall"),
        ],
    ])


def admin_sessions_keyboard(sessions: list) -> InlineKeyboardMarkup:
    """List sessions with view/kick options."""
    buttons = []
    
    for session in sessions[:10]:  # Max 10 sessions shown
        session_id = session.get("session_id", "")[:8]
        username = session.get("owner_username", "Unknown")
        listeners = session.get("listener_count", 0)
        
        buttons.append([
            InlineKeyboardButton(
                f"👁️ @{username} ({listeners}🎧)",
                callback_data=f"admin:view:{session_id}"
            ),
            InlineKeyboardButton(
                "🛑",
                callback_data=f"admin:kick:{session_id}"
            ),
        ])
    
    buttons.append([InlineKeyboardButton("◀️ Back", callback_data="admin:refresh")])
    
    return InlineKeyboardMarkup(buttons)


def admin_confirm_kick_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Confirm kicking a session."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Kick", callback_data=f"admin:kick:confirm:{session_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin:sessions"),
        ],
    ])


def admin_confirm_stopall_keyboard() -> InlineKeyboardMarkup:
    """Confirm stopping all sessions."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Stop All", callback_data="admin:stopall:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin:refresh"),
        ],
    ])
