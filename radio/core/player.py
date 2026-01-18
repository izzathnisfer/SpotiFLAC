"""
Radio Streaming Service - FFmpeg Audio Player (Phase 2)

Handles audio transcoding and streaming via FFmpeg subprocess.
Integrates with queue for continuous playback.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import AsyncIterator, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import time

import config
from core.queue_manager import SessionQueue, get_queue, Track, TrackStatus

logger = logging.getLogger(__name__)


class PlayerState(Enum):
    """Player state enumeration."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    WAITING_FOR_TRACKS = "waiting_for_tracks"


class StreamPlayer:
    """
    Manages continuous audio streaming for a session.
    Handles FFmpeg process, queue integration, and auto-advance.
    """
    
    def __init__(self, session_id: str, owner_id: int):
        self.session_id = session_id
        self.owner_id = owner_id
        self.state = PlayerState.STOPPED
        
        # FFmpeg process
        self._process: Optional[subprocess.Popen] = None
        self._lock = asyncio.Lock()
        
        # Queue
        self._queue = get_queue(session_id)
        
        # Current track info
        self.current_file: Optional[Path] = None
        self.current_track_title: str = ""
        
        # Broadcast
        self._clients: set[asyncio.Queue] = set()
        self._broadcast_task: Optional[asyncio.Task] = None
        
        # Listener tracking
        self.listener_count: int = 0
        
        # Timestamps
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
        
        # Callbacks
        self._on_track_finished: Optional[Callable[[], Awaitable[None]]] = None
        self._on_queue_empty: Optional[Callable[[], Awaitable[None]]] = None
        
        # Fallback audio control
        self._playing_fallback: bool = False

    async def _broadcast_loop(self):
        """Reading master loop: reads from FFmpeg and fans out to clients."""
        logger.info(f"Player {self.session_id}: Broadcast loop started")
        chunk_size = 4096
        loop = asyncio.get_event_loop()
        
        try:
            while self.state != PlayerState.STOPPED:
                if not self._process or not self._process.stdout:
                    await asyncio.sleep(0.1)
                    continue

                # Read chunk (blocking read in executor)
                chunk = await loop.run_in_executor(
                    None, 
                    self._process.stdout.read, 
                    chunk_size
                )
                
                if chunk:
                    self.last_activity = time.time()
                    # Fan out to all connected clients
                    for client_queue in list(self._clients):
                        try:
                            # Drop packet if client is too slow (UDP-like behavior)
                            if client_queue.full():
                                try:
                                    client_queue.get_nowait() # Remove oldest
                                except asyncio.QueueEmpty:
                                    pass
                            client_queue.put_nowait(chunk)
                        except Exception:
                            pass
                else:
                    # Stream ended (track finished)
                    if self._process.poll() is not None:
                        logger.info(f"Player {self.session_id}: Track finished (EOF)")
                        if self._on_track_finished:
                            await self._on_track_finished()
                        
                        # Auto-advance
                        async with self._lock:
                            await self._stop_process()
                            next_item = self._queue.advance()
                            if next_item:
                                await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
                            else:
                                if self._on_queue_empty:
                                    await self._on_queue_empty()
                                await self._play_fallback()
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            logger.info(f"Player {self.session_id}: Broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Player {self.session_id}: Broadcast error: {e}")
        finally:
            self._broadcast_task = None

    async def stream_audio(self) -> AsyncIterator[bytes]:
        """
        Subscribe to the broadcast stream.
        """
        # Create a client queue with small buffer (Low Latency)
        # 4096 bytes * 5 ~= 20KB ~= 0.8s of audio at 192kbps
        # Any network lag > 0.8s will cause packet drop (skip to live)
        client_queue = asyncio.Queue(maxsize=5) 
        self._clients.add(client_queue)
        
        try:
            while True:
                chunk = await client_queue.get()
                yield chunk
        finally:
            self._clients.remove(client_queue)
    
    async def _start_ffmpeg(self, audio_file: Path, title: str = "") -> bool:
        """Start FFmpeg process for a file."""
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_file}")
            return False
        
        self.current_file = audio_file
        self.current_track_title = title or audio_file.stem
        self._playing_fallback = False
        
        # FFmpeg command for streaming
        # Tuned for Low Latency: -tune zerolatency
        cmd = [
            "ffmpeg",
            "-re",
            "-i", str(audio_file),
            "-c:a", "aac",
            "-b:a", f"{config.AUDIO_BITRATE}k",
            "-ac", "2",
            "-ar", "44100",
            "-f", "adts",
            "-tune", "zerolatency", 
            "-flush_packets", "1",
            "-loglevel", "error",
            "pipe:1"
        ]
        
        logger.info(f"Player {self.session_id}: Starting '{title}'")
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0 # Unbuffered
            )
            self.state = PlayerState.PLAYING
            self.last_activity = time.time()
            
            # Start broadcast task if not running
            if not self._broadcast_task:
                 self._broadcast_task = asyncio.create_task(self._broadcast_loop())
                 
            return True
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            return False
    
    async def _play_fallback(self) -> bool:
        """Play fallback audio."""
        self._playing_fallback = True
        self.state = PlayerState.WAITING_FOR_TRACKS
        self.current_track_title = "No songs in queue..."
        
        if not config.FALLBACK_AUDIO.exists():
            return False
            
        cmd = [
            "ffmpeg",
            "-re",
            "-i", str(config.FALLBACK_AUDIO),
            "-f", "lavfi", "-t", "23", "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", f"{config.AUDIO_BITRATE}k",
            "-ac", "2",
            "-ar", "44100",
            "-f", "adts",
            "-tune", "zerolatency",
            "-flush_packets", "1",
            "-loglevel", "error",
            "pipe:1"
        ]
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            self.state = PlayerState.WAITING_FOR_TRACKS
            self.last_activity = time.time()
            
            if not self._broadcast_task:
                 self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            
            return True
        except Exception as e:
            logger.error(f"Failed to start fallback: {e}")
            return False
            
    async def _stop_process(self):
        """Stop FFmpeg process but keep broadcast loop ready."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=1)
            except:
                self._process.kill()
            self._process = None
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._process is not None and self._process.poll() is None
    
    def get_status(self) -> dict:
        """Get player status."""
        current = self._queue.get_current()
        return {
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "state": self.state.value,
            "is_playing": self.is_playing(),
            "current_track": current.to_dict() if current else None,
            "current_title": self.current_track_title,
            "playing_fallback": self._playing_fallback,
            "listener_count": self.listener_count,
            "active_streams": self._active_streams,
            "pending_tracks": self._queue.get_pending_count(),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "stream_url": config.get_stream_url(self.session_id)
        }


# Player storage
_players: dict[str, StreamPlayer] = {}


def get_player(session_id: str) -> Optional[StreamPlayer]:
    """Get a player by session ID."""
    return _players.get(session_id)


def create_player(session_id: str, owner_id: int) -> StreamPlayer:
    """Create a new player for a session."""
    player = StreamPlayer(session_id, owner_id)
    _players[session_id] = player
    logger.info(f"Created player for session {session_id}")
    return player


def remove_player(session_id: str) -> bool:
    """Remove a player."""
    if session_id in _players:
        del _players[session_id]
        logger.info(f"Removed player for session {session_id}")
        return True
    return False


def get_all_players() -> list[StreamPlayer]:
    """Get all active players."""
    return list(_players.values())
