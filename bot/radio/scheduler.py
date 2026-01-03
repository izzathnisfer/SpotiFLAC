"""
Radio Scheduler
Handles time-based events: session expiration, warnings, and notifications.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, Awaitable

from pyrogram import Client

from .constants import (
    WARNING_THRESHOLD,
    MAX_SESSION_DURATION,
    EVENT_SESSION_STOP,
)

logger = logging.getLogger(__name__)


class RadioScheduler:
    """
    Manages scheduled events for radio sessions.
    Handles:
    - Session expiration
    - 1-hour warning at 5 hours
    - Last track notification
    """
    
    _instance: Optional["RadioScheduler"] = None
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, asyncio.Task]] = {}  # session_id -> {event_name: task}
        self._bot_client: Optional[Client] = None
        self._on_session_expire: Optional[Callable[[str], Awaitable[None]]] = None
    
    @classmethod
    def get_instance(cls) -> "RadioScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_bot_client(self, client: Client):
        """Set the Pyrogram client for sending notifications."""
        self._bot_client = client
    
    def set_expire_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Set callback to call when session expires."""
        self._on_session_expire = callback
    
    def _ensure_session(self, session_id: str):
        """Ensure task dict exists for session."""
        if session_id not in self._tasks:
            self._tasks[session_id] = {}
    
    async def schedule_expiration(self, session_id: str, user_id: int, expires_at: datetime):
        """
        Schedule session expiration.
        Will stop the session when expires_at is reached.
        """
        self._ensure_session(session_id)
        
        # Cancel existing expiration task
        if "expiration" in self._tasks[session_id]:
            self._tasks[session_id]["expiration"].cancel()
        
        # Calculate delay
        delay = (expires_at - datetime.now()).total_seconds()
        if delay <= 0:
            # Already expired
            await self._on_expire(session_id, user_id)
            return
        
        # Create task
        task = asyncio.create_task(self._expiration_task(session_id, user_id, delay))
        self._tasks[session_id]["expiration"] = task
        
        logger.info(f"Scheduled expiration for session {session_id} in {delay:.0f}s")
    
    async def _expiration_task(self, session_id: str, user_id: int, delay: float):
        """Task that waits and then expires the session."""
        try:
            await asyncio.sleep(delay)
            await self._on_expire(session_id, user_id)
        except asyncio.CancelledError:
            logger.debug(f"Expiration task cancelled for session {session_id}")
    
    async def _on_expire(self, session_id: str, user_id: int):
        """Called when session expires."""
        logger.info(f"Session {session_id} expired")
        
        # Notify user
        await self._notify_user(user_id, "⏰ Your radio session has reached the time limit and will stop now.")
        
        # Call expire callback
        if self._on_session_expire:
            await self._on_session_expire(session_id)
    
    async def schedule_warning(self, session_id: str, user_id: int, warn_at: datetime):
        """
        Schedule the 1-hour warning notification.
        Sent when session reaches 5 hours.
        """
        self._ensure_session(session_id)
        
        # Cancel existing warning task
        if "warning" in self._tasks[session_id]:
            self._tasks[session_id]["warning"].cancel()
        
        # Calculate delay
        delay = (warn_at - datetime.now()).total_seconds()
        if delay <= 0:
            # Warning time already passed
            return
        
        # Create task
        task = asyncio.create_task(self._warning_task(session_id, user_id, delay))
        self._tasks[session_id]["warning"] = task
        
        logger.info(f"Scheduled warning for session {session_id} in {delay:.0f}s")
    
    async def _warning_task(self, session_id: str, user_id: int, delay: float):
        """Task that waits and then sends warning."""
        try:
            await asyncio.sleep(delay)
            await self._notify_user(
                user_id, 
                "⚠️ **Radio Session Warning**\n\n"
                "Your radio session will end in **1 hour**.\n"
                "Add more tracks to extend or the server will stop automatically."
            )
        except asyncio.CancelledError:
            logger.debug(f"Warning task cancelled for session {session_id}")
    
    async def notify_last_track(self, session_id: str, user_id: int, track_name: str):
        """Send notification when the last track starts playing."""
        await self._notify_user(
            user_id,
            f"🎵 **Last Track Playing**\n\n"
            f"Now playing: **{track_name}**\n\n"
            "This is the last track in your queue. "
            "The server will stop after this track finishes.\n\n"
            "Add more tracks with /radio to continue streaming."
        )
    
    async def notify_empty_queue(self, session_id: str, user_id: int):
        """Send notification when queue is empty."""
        await self._notify_user(
            user_id,
            "📭 **Queue Empty**\n\n"
            "Nothing more to play. The server will stop now.\n\n"
            "Start a new session with /radio_start"
        )
    
    async def notify_session_started(self, session_id: str, user_id: int, stream_url: str):
        """Send notification when session starts."""
        await self._notify_user(
            user_id,
            f"📻 **Radio Session Started!**\n\n"
            f"🔗 **Stream URL:**\n`{stream_url}`\n\n"
            f"Share this link with anyone who wants to listen.\n"
            f"Open in VLC or any media player.\n\n"
            f"⏱ Session duration: 30 minutes (add tracks to extend up to 6 hours)\n\n"
            f"Use /radio to control playback and manage your queue."
        )
    
    async def notify_session_stopped(self, session_id: str, user_id: int, reason: str = ""):
        """Send notification when session stops."""
        reason_text = f"\nReason: {reason}" if reason else ""
        await self._notify_user(
            user_id,
            f"⏹️ **Radio Session Ended**{reason_text}\n\n"
            "Thanks for using SpotiFLAC Radio!\n"
            "Start a new session anytime with /radio_start"
        )
    
    async def _notify_user(self, user_id: int, message: str):
        """Send a notification to a user via Telegram."""
        if not self._bot_client:
            logger.warning("Bot client not set, cannot send notification")
            return
        
        try:
            await self._bot_client.send_message(user_id, message)
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
    
    async def cancel_all(self, session_id: str):
        """Cancel all scheduled tasks for a session."""
        if session_id in self._tasks:
            for task_name, task in self._tasks[session_id].items():
                if not task.done():
                    task.cancel()
                    logger.debug(f"Cancelled {task_name} task for session {session_id}")
            del self._tasks[session_id]
    
    async def reschedule_expiration(self, session_id: str, user_id: int, new_expires_at: datetime):
        """
        Reschedule expiration with new time.
        Called when session is extended by adding tracks.
        """
        await self.schedule_expiration(session_id, user_id, new_expires_at)
        
        # Also schedule warning if we're past warning threshold
        total_seconds = (new_expires_at - datetime.now()).total_seconds()
        if total_seconds > (MAX_SESSION_DURATION - WARNING_THRESHOLD):
            warn_at = new_expires_at - timedelta(hours=1)
            await self.schedule_warning(session_id, user_id, warn_at)
    
    async def cleanup(self):
        """Cancel all tasks for all sessions."""
        for session_id in list(self._tasks.keys()):
            await self.cancel_all(session_id)


def get_scheduler() -> RadioScheduler:
    """Get the global radio scheduler."""
    return RadioScheduler.get_instance()
