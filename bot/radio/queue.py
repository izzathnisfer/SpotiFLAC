"""
Radio Queue Manager
Manages the track queue for radio sessions.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

from .constants import (
    MAX_SESSION_DURATION,
    QUEUE_STATUS_PENDING,
    QUEUE_STATUS_PLAYING,
    QUEUE_STATUS_PLAYED,
    QUEUE_STATUS_SKIPPED,
    QUEUE_STATUS_FAILED,
    EVENT_TRACK_ADD,
    EVENT_TRACK_REMOVE,
)

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """Represents a single track in the radio queue."""
    
    id: int  # Auto-incremented database ID
    session_id: str
    position: int
    track_isrc: str
    track_name: str
    artist_name: str
    album_name: str = ""
    duration: int = 0  # Duration in seconds
    file_path: Optional[str] = None
    status: str = QUEUE_STATUS_PENDING
    added_at: datetime = field(default_factory=datetime.now)
    spotify_id: str = ""
    cover_url: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "position": self.position,
            "track_isrc": self.track_isrc,
            "track_name": self.track_name,
            "artist_name": self.artist_name,
            "album_name": self.album_name,
            "duration": self.duration,
            "file_path": self.file_path,
            "status": self.status,
            "added_at": self.added_at.isoformat(),
            "spotify_id": self.spotify_id,
            "cover_url": self.cover_url,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueueItem":
        """Create QueueItem from dictionary."""
        return cls(
            id=data.get("id", 0),
            session_id=data["session_id"],
            position=data["position"],
            track_isrc=data["track_isrc"],
            track_name=data["track_name"],
            artist_name=data["artist_name"],
            album_name=data.get("album_name", ""),
            duration=data.get("duration", 0),
            file_path=data.get("file_path"),
            status=data.get("status", QUEUE_STATUS_PENDING),
            added_at=datetime.fromisoformat(data["added_at"]) if data.get("added_at") else datetime.now(),
            spotify_id=data.get("spotify_id", ""),
            cover_url=data.get("cover_url", ""),
        )
    
    def display_name(self) -> str:
        """Get display name for the track."""
        return f"{self.artist_name} - {self.track_name}"


class QueueManager:
    """
    Manages track queues for all radio sessions.
    """
    
    _instance: Optional["QueueManager"] = None
    
    def __init__(self):
        # session_id -> list of QueueItems
        self._queues: Dict[str, List[QueueItem]] = {}
        self._next_id = 1  # Simple counter for queue item IDs
    
    @classmethod
    def get_instance(cls) -> "QueueManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _get_next_id(self) -> int:
        """Get next unique ID for queue items."""
        id = self._next_id
        self._next_id += 1
        return id
    
    def _ensure_queue(self, session_id: str) -> List[QueueItem]:
        """Ensure queue exists for session."""
        if session_id not in self._queues:
            self._queues[session_id] = []
        return self._queues[session_id]
    
    async def add_track(
        self,
        session_id: str,
        track_isrc: str,
        track_name: str,
        artist_name: str,
        album_name: str = "",
        duration: int = 0,
        spotify_id: str = "",
        cover_url: str = "",
    ) -> Optional[QueueItem]:
        """
        Add a track to the queue.
        Returns the QueueItem if successful, None if would exceed time limit.
        """
        queue = self._ensure_queue(session_id)
        
        # Check if adding this track would exceed 6-hour limit
        if await self.will_exceed_limit(session_id, duration):
            logger.warning(f"Cannot add track: would exceed 6-hour limit")
            return None
        
        # Calculate next position
        next_position = len(queue) + 1
        
        # Create queue item
        item = QueueItem(
            id=self._get_next_id(),
            session_id=session_id,
            position=next_position,
            track_isrc=track_isrc,
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            duration=duration,
            spotify_id=spotify_id,
            cover_url=cover_url,
            status=QUEUE_STATUS_PENDING,
        )
        
        queue.append(item)
        logger.info(f"Added track '{item.display_name()}' to session {session_id} at position {next_position}")
        
        return item
    
    async def remove_track(self, session_id: str, position: int) -> bool:
        """
        Remove a track from the queue by position.
        Reorders remaining tracks.
        """
        queue = self._ensure_queue(session_id)
        
        # Find track at position
        track_index = None
        for i, item in enumerate(queue):
            if item.position == position:
                track_index = i
                break
        
        if track_index is None:
            return False
        
        # Remove the track
        removed = queue.pop(track_index)
        
        # Reorder remaining tracks
        for i, item in enumerate(queue):
            item.position = i + 1
        
        logger.info(f"Removed track '{removed.display_name()}' from session {session_id}")
        return True
    
    async def move_track(self, session_id: str, from_pos: int, to_pos: int) -> bool:
        """
        Move a track from one position to another.
        """
        queue = self._ensure_queue(session_id)
        
        if from_pos < 1 or from_pos > len(queue) or to_pos < 1 or to_pos > len(queue):
            return False
        
        if from_pos == to_pos:
            return True
        
        # Find the track to move
        track_to_move = None
        track_index = None
        for i, item in enumerate(queue):
            if item.position == from_pos:
                track_to_move = item
                track_index = i
                break
        
        if track_to_move is None:
            return False
        
        # Remove from current position
        queue.pop(track_index)
        
        # Insert at new position
        new_index = to_pos - 1
        queue.insert(new_index, track_to_move)
        
        # Reorder all positions
        for i, item in enumerate(queue):
            item.position = i + 1
        
        logger.info(f"Moved track from position {from_pos} to {to_pos} in session {session_id}")
        return True
    
    async def shuffle_queue(self, session_id: str, preserve_current: bool = True) -> bool:
        """
        Shuffle the queue randomly.
        If preserve_current is True, keeps the currently playing track in place.
        """
        queue = self._ensure_queue(session_id)
        
        if len(queue) <= 1:
            return True
        
        # Find currently playing track
        current_track = None
        current_index = None
        if preserve_current:
            for i, item in enumerate(queue):
                if item.status == QUEUE_STATUS_PLAYING:
                    current_track = item
                    current_index = i
                    break
        
        # Remove current track if exists
        if current_track:
            queue.pop(current_index)
        
        # Shuffle remaining tracks
        random.shuffle(queue)
        
        # Reinsert current track at the beginning
        if current_track:
            queue.insert(0, current_track)
        
        # Reorder positions
        for i, item in enumerate(queue):
            item.position = i + 1
        
        logger.info(f"Shuffled queue for session {session_id}")
        return True
    
    async def get_queue(self, session_id: str) -> List[QueueItem]:
        """Get all tracks in the queue ordered by position."""
        queue = self._ensure_queue(session_id)
        return sorted(queue, key=lambda x: x.position)
    
    async def get_current_track(self, session_id: str) -> Optional[QueueItem]:
        """Get the currently playing track."""
        queue = self._ensure_queue(session_id)
        for item in queue:
            if item.status == QUEUE_STATUS_PLAYING:
                return item
        return None
    
    async def get_next_track(self, session_id: str, repeat: bool = False) -> Optional[QueueItem]:
        """
        Get the next track to play.
        If repeat is True and we're at the end, return the first track.
        """
        queue = await self.get_queue(session_id)
        
        if not queue:
            return None
        
        # Find first pending track
        for item in queue:
            if item.status == QUEUE_STATUS_PENDING:
                return item
        
        # If repeat is enabled, reset all played tracks and return first
        if repeat:
            for item in queue:
                if item.status == QUEUE_STATUS_PLAYED:
                    item.status = QUEUE_STATUS_PENDING
            if queue:
                return queue[0]
        
        return None
    
    async def mark_track_playing(self, session_id: str, position: int) -> bool:
        """Mark a track as currently playing."""
        queue = self._ensure_queue(session_id)
        
        # First, mark any currently playing track as played
        for item in queue:
            if item.status == QUEUE_STATUS_PLAYING:
                item.status = QUEUE_STATUS_PLAYED
        
        # Mark the new track as playing
        for item in queue:
            if item.position == position:
                item.status = QUEUE_STATUS_PLAYING
                logger.info(f"Now playing: '{item.display_name()}' in session {session_id}")
                return True
        
        return False
    
    async def mark_track_played(self, session_id: str, position: int) -> bool:
        """Mark a track as played."""
        queue = self._ensure_queue(session_id)
        for item in queue:
            if item.position == position:
                item.status = QUEUE_STATUS_PLAYED
                return True
        return False
    
    async def mark_track_skipped(self, session_id: str, position: int) -> bool:
        """Mark a track as skipped."""
        queue = self._ensure_queue(session_id)
        for item in queue:
            if item.position == position:
                item.status = QUEUE_STATUS_SKIPPED
                return True
        return False
    
    async def mark_track_failed(self, session_id: str, position: int) -> bool:
        """Mark a track as failed."""
        queue = self._ensure_queue(session_id)
        for item in queue:
            if item.position == position:
                item.status = QUEUE_STATUS_FAILED
                return True
        return False
    
    async def set_track_file_path(self, session_id: str, position: int, file_path: str) -> bool:
        """Set the cached file path for a track."""
        queue = self._ensure_queue(session_id)
        for item in queue:
            if item.position == position:
                item.file_path = file_path
                return True
        return False
    
    async def get_total_duration(self, session_id: str) -> int:
        """Get total duration of all tracks in seconds."""
        queue = self._ensure_queue(session_id)
        return sum(item.duration for item in queue)
    
    async def get_remaining_duration(self, session_id: str) -> int:
        """Get remaining duration of pending tracks in seconds."""
        queue = self._ensure_queue(session_id)
        return sum(
            item.duration for item in queue 
            if item.status in (QUEUE_STATUS_PENDING, QUEUE_STATUS_PLAYING)
        )
    
    async def will_exceed_limit(self, session_id: str, new_duration: int) -> bool:
        """Check if adding a track with given duration would exceed 6-hour limit."""
        current_total = await self.get_total_duration(session_id)
        return (current_total + new_duration) > MAX_SESSION_DURATION
    
    async def get_queue_length(self, session_id: str) -> int:
        """Get number of tracks in the queue."""
        return len(self._ensure_queue(session_id))
    
    async def is_last_track(self, session_id: str) -> bool:
        """Check if the currently playing track is the last one."""
        queue = await self.get_queue(session_id)
        pending_count = sum(1 for item in queue if item.status == QUEUE_STATUS_PENDING)
        return pending_count == 0
    
    async def clear_queue(self, session_id: str):
        """Clear all tracks from the queue."""
        self._queues[session_id] = []
        logger.info(f"Cleared queue for session {session_id}")
    
    async def cleanup_session(self, session_id: str):
        """Remove all queue data for a session."""
        if session_id in self._queues:
            del self._queues[session_id]
            logger.info(f"Cleaned up queue for session {session_id}")


# Convenience function
def get_queue_manager() -> QueueManager:
    """Get the global queue manager instance."""
    return QueueManager.get_instance()
