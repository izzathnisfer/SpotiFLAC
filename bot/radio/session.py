"""
Radio Session Manager
Handles session lifecycle: creation, state management, and cleanup.
"""

import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict

from .constants import (
    MAX_SESSION_DURATION,
    DEFAULT_SESSION_DURATION,
    STREAM_PORT_START,
    STREAM_PORT_END,
    DEFAULT_BITRATE,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_PAUSED,
    SESSION_STATUS_STOPPED,
    EVENT_SESSION_START,
    EVENT_SESSION_STOP,
    EVENT_SESSION_PAUSE,
    EVENT_SESSION_RESUME,
)

logger = logging.getLogger(__name__)


@dataclass
class RadioSession:
    """Represents an active radio streaming session."""
    
    id: str
    user_id: int
    stream_port: int
    stream_url: str
    bitrate: int = DEFAULT_BITRATE
    status: str = SESSION_STATUS_ACTIVE
    repeat_enabled: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(seconds=DEFAULT_SESSION_DURATION))
    last_activity: datetime = field(default_factory=datetime.now)
    current_track_index: int = 0
    current_track_position: float = 0.0  # Playback position in seconds
    total_duration_played: float = 0.0   # Cumulative seconds streamed
    
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status == SESSION_STATUS_ACTIVE
    
    def is_paused(self) -> bool:
        """Check if session is paused."""
        return self.status == SESSION_STATUS_PAUSED
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() > self.expires_at
    
    def get_remaining_seconds(self) -> int:
        """Get remaining seconds until expiration."""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def can_extend(self, additional_seconds: int) -> bool:
        """Check if session can be extended by given seconds."""
        new_duration = self.total_duration_played + additional_seconds
        return new_duration <= MAX_SESSION_DURATION
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stream_port": self.stream_port,
            "stream_url": self.stream_url,
            "bitrate": self.bitrate,
            "status": self.status,
            "repeat_enabled": 1 if self.repeat_enabled else 0,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "current_track_index": self.current_track_index,
            "current_track_position": self.current_track_position,
            "total_duration_played": self.total_duration_played,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RadioSession":
        """Create RadioSession from dictionary."""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            stream_port=data["stream_port"],
            stream_url=data["stream_url"],
            bitrate=data.get("bitrate", DEFAULT_BITRATE),
            status=data.get("status", SESSION_STATUS_ACTIVE),
            repeat_enabled=bool(data.get("repeat_enabled", 0)),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else datetime.now(),
            last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else datetime.now(),
            current_track_index=data.get("current_track_index", 0),
            current_track_position=data.get("current_track_position", 0.0),
            total_duration_played=data.get("total_duration_played", 0.0),
        )


class SessionManager:
    """
    Manages all radio streaming sessions.
    Singleton pattern - use get_instance() to get the manager.
    """
    
    _instance: Optional["SessionManager"] = None
    
    def __init__(self):
        self._sessions: Dict[str, RadioSession] = {}  # session_id -> RadioSession
        self._user_sessions: Dict[int, str] = {}      # user_id -> session_id
        self._used_ports: set = set()
        self._lock = asyncio.Lock()
        self._public_host: str = "0.0.0.0"  # Will be set from config
    
    @classmethod
    def get_instance(cls) -> "SessionManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_public_host(self, host: str):
        """Set the public host for stream URLs."""
        self._public_host = host
    
    async def create_session(
        self, 
        user_id: int, 
        bitrate: int = DEFAULT_BITRATE
    ) -> Optional[RadioSession]:
        """
        Create a new radio session for a user.
        Returns None if user already has an active session.
        """
        async with self._lock:
            # Check one-session-per-user rule
            if user_id in self._user_sessions:
                existing_id = self._user_sessions[user_id]
                if existing_id in self._sessions:
                    existing = self._sessions[existing_id]
                    if not existing.is_expired() and existing.status != SESSION_STATUS_STOPPED:
                        logger.warning(f"User {user_id} already has active session {existing_id}")
                        return None
            
            # Find available port
            port = self._find_available_port()
            if port is None:
                logger.error("No available ports for new session")
                return None
            
            # Generate session ID and URL
            session_id = str(uuid.uuid4())
            stream_url = f"http://{self._public_host}:{port}/"
            
            # Create session
            session = RadioSession(
                id=session_id,
                user_id=user_id,
                stream_port=port,
                stream_url=stream_url,
                bitrate=bitrate,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=DEFAULT_SESSION_DURATION),
            )
            
            # Track session
            self._sessions[session_id] = session
            self._user_sessions[user_id] = session_id
            self._used_ports.add(port)
            
            logger.info(f"Created session {session_id} for user {user_id} on port {port}")
            
            # Log event
            await self._log_event(session_id, EVENT_SESSION_START, {
                "user_id": user_id,
                "port": port,
                "bitrate": bitrate,
            })
            
            return session
    
    def _find_available_port(self) -> Optional[int]:
        """Find an available port in the configured range."""
        for port in range(STREAM_PORT_START, STREAM_PORT_END + 1):
            if port not in self._used_ports:
                return port
        return None
    
    async def get_session(self, session_id: str) -> Optional[RadioSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    async def get_user_session(self, user_id: int) -> Optional[RadioSession]:
        """Get active session for a user."""
        session_id = self._user_sessions.get(user_id)
        if session_id:
            session = self._sessions.get(session_id)
            if session and session.status != SESSION_STATUS_STOPPED:
                return session
        return None
    
    async def stop_session(self, session_id: str, reason: str = "user_request") -> bool:
        """
        Stop a session and clean up resources.
        Returns True if session was stopped, False if not found.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            # Update status
            session.status = SESSION_STATUS_STOPPED
            
            # Release port
            self._used_ports.discard(session.stream_port)
            
            # Remove from tracking
            if session.user_id in self._user_sessions:
                del self._user_sessions[session.user_id]
            
            logger.info(f"Stopped session {session_id}: {reason}")
            
            # Log event
            await self._log_event(session_id, EVENT_SESSION_STOP, {
                "reason": reason,
                "total_duration": session.total_duration_played,
            })
            
            return True
    
    async def pause_session(self, session_id: str) -> bool:
        """Pause a session."""
        session = self._sessions.get(session_id)
        if not session or session.status != SESSION_STATUS_ACTIVE:
            return False
        
        session.status = SESSION_STATUS_PAUSED
        logger.info(f"Paused session {session_id}")
        
        await self._log_event(session_id, EVENT_SESSION_PAUSE, {})
        return True
    
    async def resume_session(self, session_id: str) -> bool:
        """Resume a paused session."""
        session = self._sessions.get(session_id)
        if not session or session.status != SESSION_STATUS_PAUSED:
            return False
        
        session.status = SESSION_STATUS_ACTIVE
        session.last_activity = datetime.now()
        logger.info(f"Resumed session {session_id}")
        
        await self._log_event(session_id, EVENT_SESSION_RESUME, {})
        return True
    
    async def extend_session(self, session_id: str, additional_seconds: int) -> bool:
        """
        Extend session expiration time.
        Returns False if extension would exceed 6-hour limit.
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        if not session.can_extend(additional_seconds):
            logger.warning(f"Cannot extend session {session_id}: would exceed 6hr limit")
            return False
        
        session.expires_at = session.expires_at + timedelta(seconds=additional_seconds)
        session.last_activity = datetime.now()
        
        logger.info(f"Extended session {session_id} by {additional_seconds}s")
        return True
    
    async def update_playback_position(self, session_id: str, position: float, duration_added: float = 0):
        """Update the current playback position and total duration."""
        session = self._sessions.get(session_id)
        if session:
            session.current_track_position = position
            session.total_duration_played += duration_added
            session.last_activity = datetime.now()
    
    async def set_current_track(self, session_id: str, track_index: int):
        """Set the current track index."""
        session = self._sessions.get(session_id)
        if session:
            session.current_track_index = track_index
            session.current_track_position = 0.0
            session.last_activity = datetime.now()
    
    async def toggle_repeat(self, session_id: str) -> bool:
        """Toggle repeat mode. Returns new state."""
        session = self._sessions.get(session_id)
        if session:
            session.repeat_enabled = not session.repeat_enabled
            return session.repeat_enabled
        return False
    
    async def cleanup_orphaned_sessions(self) -> int:
        """
        Clean up sessions that expired or were orphaned.
        Called on startup. Returns count of cleaned sessions.
        """
        count = 0
        async with self._lock:
            expired_ids = []
            
            for session_id, session in self._sessions.items():
                if session.is_expired() or session.status == SESSION_STATUS_STOPPED:
                    expired_ids.append(session_id)
            
            for session_id in expired_ids:
                session = self._sessions.pop(session_id, None)
                if session:
                    self._used_ports.discard(session.stream_port)
                    self._user_sessions.pop(session.user_id, None)
                    count += 1
                    logger.info(f"Cleaned up orphaned session {session_id}")
        
        return count
    
    async def get_all_active_sessions(self) -> list[RadioSession]:
        """Get all active sessions."""
        return [
            s for s in self._sessions.values() 
            if s.status in (SESSION_STATUS_ACTIVE, SESSION_STATUS_PAUSED)
        ]
    
    async def _log_event(self, session_id: str, event_type: str, event_data: dict):
        """Log an event to the database."""
        # TODO: Implement database logging
        # For now, just log to console
        import json
        logger.debug(f"Event [{session_id}] {event_type}: {json.dumps(event_data)}")


# Convenience function to get the session manager
def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    return SessionManager.get_instance()
