"""
Radio Streaming Service - Session Manager

Manages user streaming sessions with lifecycle control.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Awaitable
from enum import Enum

import config

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    PAUSED = "paused"
    WAITING_FOR_TRACKS = "waiting_for_tracks"  # Queue empty, playing fallback
    STOPPED = "stopped"


@dataclass
class Session:
    """
    Represents a user's streaming session.
    Each session has its own queue and playback state.
    """
    id: str
    owner_id: int
    owner_username: Optional[str] = None
    
    # State
    state: SessionState = SessionState.ACTIVE
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    queue_empty_since: Optional[float] = None  # For timeout tracking
    
    # Listener tracking
    listener_count: int = 0
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def mark_queue_empty(self):
        """Mark the moment queue became empty."""
        if self.queue_empty_since is None:
            self.queue_empty_since = time.time()
            self.state = SessionState.WAITING_FOR_TRACKS
            logger.info(f"Session {self.id}: Queue empty, starting timeout countdown")
    
    def mark_queue_has_tracks(self):
        """Reset queue empty state when tracks are added."""
        self.queue_empty_since = None
        if self.state == SessionState.WAITING_FOR_TRACKS:
            self.state = SessionState.ACTIVE
    
    def is_timeout_expired(self) -> bool:
        """Check if session should be terminated due to inactivity."""
        if self.queue_empty_since is None:
            return False
        elapsed = time.time() - self.queue_empty_since
        timeout_seconds = config.SESSION_TIMEOUT_MINUTES * 60
        return elapsed >= timeout_seconds
    
    def get_timeout_remaining(self) -> Optional[int]:
        """Get remaining seconds before timeout, or None if not in timeout."""
        if self.queue_empty_since is None:
            return None
        elapsed = time.time() - self.queue_empty_since
        timeout_seconds = config.SESSION_TIMEOUT_MINUTES * 60
        remaining = timeout_seconds - elapsed
        return max(0, int(remaining))
    
    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "state": self.state.value,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "listener_count": self.listener_count,
            "timeout_remaining": self.get_timeout_remaining(),
            "stream_url": config.get_stream_url(self.id)
        }


class SessionManager:
    """
    Manages all streaming sessions.
    Enforces max session limit and handles lifecycle.
    """
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[int, str] = {}  # user_id -> session_id mapping
        self._lock = asyncio.Lock()
        self._timeout_task: Optional[asyncio.Task] = None
        self._on_session_timeout: Optional[Callable[[Session], Awaitable[None]]] = None
    
    async def start(self, on_timeout: Optional[Callable[[Session], Awaitable[None]]] = None):
        """Start the session manager background tasks."""
        self._on_session_timeout = on_timeout
        self._timeout_task = asyncio.create_task(self._timeout_monitor())
        logger.info("Session manager started")
    
    async def stop(self):
        """Stop the session manager."""
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
        
        # Stop all sessions
        async with self._lock:
            for session in list(self._sessions.values()):
                await self._cleanup_session(session)
            self._sessions.clear()
            self._user_sessions.clear()
        
        logger.info("Session manager stopped")
    
    async def create_session(self, user_id: int, username: Optional[str] = None) -> Optional[Session]:
        """
        Create a new streaming session for a user.
        Returns None if max sessions reached or user already has a session.
        """
        async with self._lock:
            # Check if user already has a session
            if user_id in self._user_sessions:
                existing_id = self._user_sessions[user_id]
                if existing_id in self._sessions:
                    logger.info(f"User {user_id} already has session {existing_id}")
                    return self._sessions[existing_id]
            
            # Check max sessions limit
            if len(self._sessions) >= config.MAX_SESSIONS:
                logger.warning(f"Max sessions ({config.MAX_SESSIONS}) reached")
                return None
            
            # Create new session
            session_id = str(uuid.uuid4())[:8]  # Short UUID for readability
            session = Session(
                id=session_id,
                owner_id=user_id,
                owner_username=username
            )
            
            self._sessions[session_id] = session
            self._user_sessions[user_id] = session_id
            
            logger.info(f"Created session {session_id} for user {user_id} ({username})")
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    async def get_session_by_user(self, user_id: int) -> Optional[Session]:
        """Get a user's session."""
        session_id = self._user_sessions.get(user_id)
        if session_id:
            return self._sessions.get(session_id)
        return None
    
    async def remove_session(self, session_id: str) -> bool:
        """Remove a session."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            await self._cleanup_session(session)
            del self._sessions[session_id]
            
            # Remove user mapping
            if session.owner_id in self._user_sessions:
                if self._user_sessions[session.owner_id] == session_id:
                    del self._user_sessions[session.owner_id]
            
            logger.info(f"Removed session {session_id}")
            return True
    
    async def remove_session_by_user(self, user_id: int) -> bool:
        """Remove a user's session."""
        session_id = self._user_sessions.get(user_id)
        if session_id:
            return await self.remove_session(session_id)
        return False
    
    def get_all_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return list(self._sessions.values())
    
    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self._sessions)
    
    def get_total_listeners(self) -> int:
        """Get total listener count across all sessions."""
        return sum(s.listener_count for s in self._sessions.values())
    
    async def _cleanup_session(self, session: Session):
        """Internal cleanup for a session."""
        session.state = SessionState.STOPPED
        # Additional cleanup will be added later (FFmpeg process, etc.)
    
    async def _timeout_monitor(self):
        """Background task to monitor and close timed-out sessions."""
        logger.info("Timeout monitor started")
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                async with self._lock:
                    timed_out = [
                        s for s in self._sessions.values()
                        if s.is_timeout_expired()
                    ]
                
                for session in timed_out:
                    logger.info(f"Session {session.id} timed out")
                    if self._on_session_timeout:
                        await self._on_session_timeout(session)
                    await self.remove_session(session.id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in timeout monitor: {e}")
        
        logger.info("Timeout monitor stopped")


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
