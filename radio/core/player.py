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
        
        # Listener tracking
        self.listener_count: int = 0
        self._active_streams: int = 0
        
        # Timestamps
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
        
        # Callbacks
        self._on_track_finished: Optional[Callable[[], Awaitable[None]]] = None
        self._on_queue_empty: Optional[Callable[[], Awaitable[None]]] = None
        
        # Fallback audio control
        self._playing_fallback: bool = False
        
    @property
    def queue(self) -> SessionQueue:
        return self._queue
    
    def set_callbacks(
        self,
        on_track_finished: Optional[Callable[[], Awaitable[None]]] = None,
        on_queue_empty: Optional[Callable[[], Awaitable[None]]] = None
    ):
        """Set event callbacks."""
        self._on_track_finished = on_track_finished
        self._on_queue_empty = on_queue_empty
    
    async def start(self) -> bool:
        """Start the player, playing from queue or fallback."""
        async with self._lock:
            # Try to play from queue first
            current = self._queue.get_current()
            if current and current.status == TrackStatus.PLAYING:
                # Already have a current track
                return await self._start_ffmpeg(current.track.file_path, current.track.title)
            
            # Try to advance to first track
            next_item = self._queue.advance()
            if next_item:
                return await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
            
            # No tracks, play fallback
            return await self._play_fallback()
    
    async def add_track(self, track: Track):
        """Add a track to the queue and start playing if needed."""
        item = self._queue.add_track(track)
        
        logger.info(f"Player {self.session_id}: Added track '{track.title}'. State: {self.state}")
        
        # If we're waiting for tracks, start playing
        if self.state == PlayerState.WAITING_FOR_TRACKS or self.state == PlayerState.STOPPED:
            logger.info(f"Player {self.session_id}: Interrupting fallback/idle...")
            async with self._lock:
                await self._stop_process()
                next_item = self._queue.advance()
                if next_item:
                    logger.info(f"Player {self.session_id}: Advancing to '{next_item.track.title}'")
                    success = await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
                    if not success:
                        logger.error(f"Player {self.session_id}: Failed to start FFmpeg for '{next_item.track.title}'")
                else:
                    logger.warning(f"Player {self.session_id}: Advance failed (Queue empty?)")
        else:
             logger.info(f"Player {self.session_id}: Not interrupting. State is {self.state}")
        
        return item
    
    async def skip(self) -> bool:
        """Skip current track and play next."""
        async with self._lock:
            await self._stop_process()
            next_item = self._queue.skip()
            
            if next_item:
                return await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
            else:
                # No more tracks
                return await self._play_fallback()
    
    async def pause(self):
        """Pause playback."""
        self.state = PlayerState.PAUSED
        logger.info(f"Player {self.session_id}: Paused")
    
    async def resume(self):
        """Resume playback."""
        if self.state == PlayerState.PAUSED:
            self.state = PlayerState.PLAYING
            logger.info(f"Player {self.session_id}: Resumed")
    
    async def stop(self):
        """Stop the player completely."""
        async with self._lock:
            await self._stop_process()
            self.state = PlayerState.STOPPED
            self.current_file = None
            self.current_track_title = ""
        logger.info(f"Player {self.session_id}: Stopped")
    
    async def _start_ffmpeg(self, audio_file: Path, title: str = "") -> bool:
        """Start FFmpeg process for a file."""
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_file}")
            return False
        
        self.current_file = audio_file
        self.current_track_title = title or audio_file.stem
        self._playing_fallback = False
        
        # FFmpeg command for streaming
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
        
        logger.info(f"Player {self.session_id}: Starting '{title}' ({audio_file.name})")
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            self.state = PlayerState.PLAYING
            self.last_activity = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to start FFmpeg: {e}")
            return False
    
    async def _play_fallback(self) -> bool:
        """
        Play fallback audio (no songs in queue message).
        Plays the TTS message, then 23 seconds of silence, looping every ~30 seconds.
        """
        self._playing_fallback = True
        self.state = PlayerState.WAITING_FOR_TRACKS
        self.current_track_title = "No songs in queue..."
        
        # Check if fallback audio exists
        if not config.FALLBACK_AUDIO.exists():
            logger.warning(f"Player {self.session_id}: Fallback audio not found")
            return False
        
        logger.info(f"Player {self.session_id}: Playing fallback audio (loop every 30s)")
        
        # FFmpeg command that plays the TTS then 23 seconds of silence
        # This creates a ~30 second loop (7 sec TTS + 23 sec silence)
        cmd = [
            "ffmpeg",
            "-re",  # Read at native rate
            "-i", str(config.FALLBACK_AUDIO),
            "-f", "lavfi", "-t", "23", "-i", "anullsrc=r=44100:cl=stereo",  # 23 sec silence
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",  # Concatenate audio + silence
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", f"{config.AUDIO_BITRATE}k",
            "-ac", "2",
            "-ar", "44100",
            "-f", "adts",
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
            return True
        except Exception as e:
            logger.error(f"Failed to start fallback audio: {e}")
            return False
    
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
    
    async def read_chunk(self, chunk_size: int = 4096) -> Optional[bytes]:
        """Read a chunk of audio data from the FFmpeg process."""
        if not self._process or not self._process.stdout:
            return None
        
        if self.state == PlayerState.PAUSED:
            await asyncio.sleep(0.1)
            return b'\x00' * 256  # Send minimal silence when paused
        
        try:
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
                # Stream ended (track finished)
                return None
                
        except Exception as e:
            logger.error(f"Error reading stream chunk: {e}")
            return None
    
    async def stream_audio(self) -> AsyncIterator[bytes]:
        """
        Async generator that yields audio chunks.
        Handles auto-advance to next track.
        """
        self._active_streams += 1
        try:
            while self.state != PlayerState.STOPPED:
                chunk = await self.read_chunk()
                
                if chunk:
                    yield chunk
                else:
                    # Current track/process ended
                    if self._process and self._process.poll() is not None:
                        # FFmpeg process exited
                        logger.info(f"Player {self.session_id}: Track finished")
                        
                        # Notify callback
                        if self._on_track_finished:
                            await self._on_track_finished()
                        
                        # Auto-advance to next track
                        async with self._lock:
                            await self._stop_process()
                            
                            if self._playing_fallback:
                                # Was playing fallback, check for new tracks
                                next_item = self._queue.advance()
                                if next_item:
                                    await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
                                else:
                                    # Still no tracks, replay fallback
                                    await self._play_fallback()
                            else:
                                # Normal track finished, advance queue
                                next_item = self._queue.advance()
                                if next_item:
                                    await self._start_ffmpeg(next_item.track.file_path, next_item.track.title)
                                else:
                                    # Queue empty
                                    logger.info(f"Player {self.session_id}: Queue empty")
                                    if self._on_queue_empty:
                                        await self._on_queue_empty()
                                    await self._play_fallback()
                        
                        # Small delay before continuing
                        await asyncio.sleep(0.1)
                    else:
                        # Waiting for data
                        await asyncio.sleep(0.05)
        finally:
            self._active_streams -= 1
    
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
