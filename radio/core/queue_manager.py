"""
Radio Streaming Service - Queue Manager

Manages per-session track queues with position tracking.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class TrackStatus(Enum):
    """Track status in queue."""
    PENDING = "pending"
    PLAYING = "playing"
    PLAYED = "played"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Track:
    """Represents a track in the queue."""
    id: str  # Unique track ID
    file_path: Path
    title: str
    artist: str = ""
    album: str = ""
    duration: int = 0  # seconds
    spotify_id: Optional[str] = None
    isrc: Optional[str] = None
    added_by: Optional[int] = None  # Telegram user ID
    added_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": str(self.file_path),
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "spotify_id": self.spotify_id,
            "isrc": self.isrc,
            "added_by": self.added_by,
            "added_at": self.added_at
        }


@dataclass
class QueueItem:
    """Wrapper for a track in the queue with position and status."""
    track: Track
    position: int
    status: TrackStatus = TrackStatus.PENDING
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            **self.track.to_dict()
        }


class SessionQueue:
    """
    Manages the track queue for a single session.
    Supports add, remove, skip, and position tracking.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._items: List[QueueItem] = []
        self._current_index: int = -1
        self._next_position: int = 1
    
    def add_track(self, track: Track) -> QueueItem:
        """Add a track to the end of the queue."""
        item = QueueItem(
            track=track,
            position=self._next_position
        )
        self._items.append(item)
        self._next_position += 1
        
        logger.info(f"Queue {self.session_id}: Added '{track.title}' at position {item.position}")
        return item
    
    def add_tracks(self, tracks: List[Track]) -> List[QueueItem]:
        """Add multiple tracks to the queue."""
        return [self.add_track(t) for t in tracks]
    
    def get_current(self) -> Optional[QueueItem]:
        """Get the currently playing track."""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None
    
    def get_next(self) -> Optional[QueueItem]:
        """Get the next track without advancing."""
        next_idx = self._current_index + 1
        if next_idx < len(self._items):
            return self._items[next_idx]
        return None
    
    def advance(self) -> Optional[QueueItem]:
        """
        Move to the next track in the queue.
        Returns the new current track, or None if queue is empty.
        """
        current = self.get_current()
        if current and current.status == TrackStatus.PLAYING:
            current.status = TrackStatus.PLAYED
            current.finished_at = time.time()
        
        self._current_index += 1
        
        if self._current_index < len(self._items):
            new_current = self._items[self._current_index]
            new_current.status = TrackStatus.PLAYING
            new_current.started_at = time.time()
            logger.info(f"Queue {self.session_id}: Now playing '{new_current.track.title}'")
            return new_current
        else:
            logger.info(f"Queue {self.session_id}: No more tracks")
            return None
    
    def skip(self) -> Optional[QueueItem]:
        """Skip the current track and move to next."""
        current = self.get_current()
        if current:
            current.status = TrackStatus.SKIPPED
            current.finished_at = time.time()
        return self.advance()
    
    def remove_track(self, position: int) -> bool:
        """Remove a track by position (only pending tracks)."""
        for i, item in enumerate(self._items):
            if item.position == position and item.status == TrackStatus.PENDING:
                self._items.pop(i)
                logger.info(f"Queue {self.session_id}: Removed track at position {position}")
                return True
        return False
    
    def clear_pending(self):
        """Clear all pending tracks from the queue."""
        self._items = [item for item in self._items if item.status != TrackStatus.PENDING]
        logger.info(f"Queue {self.session_id}: Cleared pending tracks")
    
    def get_pending_tracks(self) -> List[QueueItem]:
        """Get all pending tracks."""
        return [item for item in self._items if item.status == TrackStatus.PENDING]
    
    def get_all_tracks(self) -> List[QueueItem]:
        """Get all tracks in the queue."""
        return self._items.copy()
    
    def get_queue_length(self) -> int:
        """Get total number of tracks (including played)."""
        return len(self._items)
    
    def get_pending_count(self) -> int:
        """Get number of pending tracks."""
        return len(self.get_pending_tracks())
    
    def is_empty(self) -> bool:
        """Check if there are no more tracks to play."""
        return self.get_next() is None and (
            self.get_current() is None or 
            self.get_current().status != TrackStatus.PLAYING
        )
    
    def has_pending(self) -> bool:
        """Check if there are pending tracks."""
        return self.get_pending_count() > 0
    
    def to_dict(self) -> dict:
        """Convert queue to dictionary."""
        current = self.get_current()
        return {
            "session_id": self.session_id,
            "current_track": current.to_dict() if current else None,
            "pending_count": self.get_pending_count(),
            "total_count": self.get_queue_length(),
            "items": [item.to_dict() for item in self._items]
        }


# Queue storage (will be integrated with session manager)
_queues: dict[str, SessionQueue] = {}


def get_queue(session_id: str) -> SessionQueue:
    """Get or create a queue for a session."""
    if session_id not in _queues:
        _queues[session_id] = SessionQueue(session_id)
    return _queues[session_id]


def remove_queue(session_id: str) -> bool:
    """Remove a session's queue."""
    if session_id in _queues:
        del _queues[session_id]
        return True
    return False
