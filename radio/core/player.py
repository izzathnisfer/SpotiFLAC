"""
Radio Streaming Service - FFmpeg Audio Player

Handles audio transcoding and streaming via FFmpeg subprocess.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field
from enum import Enum
import time

import config

logger = logging.getLogger(__name__)


class PlayerState(Enum):
    """Player state enumeration."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class StreamSession:
    """
    Represents a single streaming session with its own FFmpeg process.
    Each user gets their own session with independent playback.
    """
    session_id: str
    owner_id: int  # Telegram user ID
    owner_username: Optional[str] = None
    
    # Playback state
    state: PlayerState = PlayerState.STOPPED
    current_file: Optional[Path] = None
    
    # FFmpeg process
    _process: Optional[subprocess.Popen] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    # Listener tracking
    listener_count: int = 0
    
    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    def __post_init__(self):
        self._lock = asyncio.Lock()
    
    async def start_stream(self, audio_file: Path) -> bool:
        """
        Start streaming an audio file through FFmpeg.
        Transcodes to 128kbps AAC for bandwidth efficiency.
        """
        async with self._lock:
            # Stop any existing process
            await self._stop_process()
            
            if not audio_file.exists():
                logger.error(f"Audio file not found: {audio_file}")
                return False
            
            self.current_file = audio_file
            
            # FFmpeg command for streaming
            # -re: Read input at native frame rate (important for live streaming)
            # -i: Input file
            # -c:a aac: Encode to AAC
            # -b:a 128k: 128kbps bitrate
            # -f adts: Output format (AAC in ADTS container - good for streaming)
            # pipe:1: Output to stdout
            cmd = [
                "ffmpeg",
                "-re",  # Read at native rate
                "-i", str(audio_file),
                "-c:a", "aac",
                "-b:a", f"{config.AUDIO_BITRATE}k",
                "-ac", "2",  # Stereo
                "-ar", "44100",  # Sample rate
                "-f", "adts",  # ADTS format for AAC streaming
                "-loglevel", "error",
                "pipe:1"
            ]
            
            logger.info(f"Starting stream for session {self.session_id}: {audio_file.name}")
            
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # Unbuffered for real-time streaming
                )
                self.state = PlayerState.PLAYING
                self.last_activity = time.time()
                return True
            except Exception as e:
                logger.error(f"Failed to start FFmpeg: {e}")
                return False
    
    async def read_chunk(self, chunk_size: int = 4096) -> Optional[bytes]:
        """
        Read a chunk of audio data from the FFmpeg process.
        Returns None if stream has ended or error occurred.
        """
        if not self._process or not self._process.stdout:
            return None
        
        if self.state == PlayerState.PAUSED:
            # When paused, return silence (AAC silence frames would be complex,
            # so we just return None and let the caller handle it)
            await asyncio.sleep(0.1)
            return None
        
        try:
            # Read in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            chunk = await loop.run_in_executor(
                None, 
                self._process.stdout.read, 
                chunk_size
            )
            
            if chunk:
                self.last_activity = time.time()
                return chunk
            else:
                # Stream ended (FFmpeg finished or file ended)
                logger.info(f"Stream ended for session {self.session_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error reading stream chunk: {e}")
            return None
    
    async def stream_audio(self) -> AsyncIterator[bytes]:
        """
        Async generator that yields audio chunks.
        Used by FastAPI StreamingResponse.
        """
        while True:
            chunk = await self.read_chunk()
            if chunk:
                yield chunk
            else:
                # Check if process is still running
                if self._process and self._process.poll() is None:
                    # Process still running, might be paused or buffering
                    await asyncio.sleep(0.05)
                    continue
                else:
                    # Process ended, track finished
                    break
    
    async def stop(self):
        """Stop the current stream."""
        async with self._lock:
            await self._stop_process()
            self.state = PlayerState.STOPPED
            self.current_file = None
    
    async def pause(self):
        """Pause playback."""
        self.state = PlayerState.PAUSED
        logger.info(f"Session {self.session_id} paused")
    
    async def resume(self):
        """Resume playback."""
        if self.state == PlayerState.PAUSED:
            self.state = PlayerState.PLAYING
            logger.info(f"Session {self.session_id} resumed")
    
    async def _stop_process(self):
        """Internal: Stop the FFmpeg process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            except Exception as e:
                logger.error(f"Error stopping FFmpeg process: {e}")
            finally:
                self._process = None
    
    def is_stream_active(self) -> bool:
        """Check if the stream is currently active."""
        return self._process is not None and self._process.poll() is None
    
    def get_status(self) -> dict:
        """Get session status as dictionary."""
        return {
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "owner_username": self.owner_username,
            "state": self.state.value,
            "current_file": str(self.current_file) if self.current_file else None,
            "listener_count": self.listener_count,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "is_active": self.is_stream_active()
        }


# Global session storage (will be replaced with proper session manager in Phase 2)
_sessions: dict[str, StreamSession] = {}


def get_session(session_id: str) -> Optional[StreamSession]:
    """Get a session by ID."""
    return _sessions.get(session_id)


def create_session(session_id: str, owner_id: int, owner_username: Optional[str] = None) -> StreamSession:
    """Create a new streaming session."""
    session = StreamSession(
        session_id=session_id,
        owner_id=owner_id,
        owner_username=owner_username
    )
    _sessions[session_id] = session
    logger.info(f"Created session {session_id} for user {owner_id}")
    return session


def remove_session(session_id: str) -> bool:
    """Remove a session."""
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info(f"Removed session {session_id}")
        return True
    return False


def get_all_sessions() -> list[StreamSession]:
    """Get all active sessions."""
    return list(_sessions.values())
