"""
Queue Handler - View and manage download queue
"""

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


# In-memory queue (would be per-user in production)
_download_queues: dict = {}


async def handle(client: Client, message: Message):
    """Handle /queue command."""
    user_id = message.from_user.id
    queue = _download_queues.get(user_id, [])
    
    if not queue:
        await message.reply("📭 Download queue is empty")
        return
    
    text = "📋 **Download Queue**\n\n"
    for i, item in enumerate(queue, 1):
        status_icon = {
            "pending": "⏳",
            "downloading": "⬇️",
            "uploading": "⬆️",
            "completed": "✅",
            "failed": "❌"
        }.get(item.get("status", "pending"), "⏳")
        
        text += f"{status_icon} {i}. {item.get('name', 'Unknown')}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Clear Completed", callback_data="q:clear")],
        [InlineKeyboardButton("⏹️ Cancel All", callback_data="q:cancel")]
    ])
    
    await message.reply(text, reply_markup=keyboard)


async def handle_cancel(client: Client, message: Message):
    """Handle /cancel command."""
    user_id = message.from_user.id
    
    if user_id in _download_queues:
        count = len(_download_queues[user_id])
        _download_queues[user_id] = []
        await message.reply(f"⏹️ Cancelled {count} items in queue")
    else:
        await message.reply("📭 No active downloads to cancel")


def add_to_queue(user_id: int, item: dict):
    """Add item to user's download queue."""
    if user_id not in _download_queues:
        _download_queues[user_id] = []
    _download_queues[user_id].append(item)


def update_queue_status(user_id: int, isrc: str, status: str):
    """Update status of a queue item."""
    queue = _download_queues.get(user_id, [])
    for item in queue:
        if item.get("isrc") == isrc:
            item["status"] = status
            break


def remove_from_queue(user_id: int, isrc: str):
    """Remove item from queue."""
    if user_id in _download_queues:
        _download_queues[user_id] = [
            i for i in _download_queues[user_id] if i.get("isrc") != isrc
        ]


def clear_completed(user_id: int):
    """Remove completed/failed items from queue."""
    if user_id in _download_queues:
        _download_queues[user_id] = [
            i for i in _download_queues[user_id]
            if i.get("status") not in ("completed", "failed")
        ]
