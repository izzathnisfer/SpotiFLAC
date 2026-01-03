"""
Radio Engine
Orchestrates the streaming pipeline: session, queue, transcoder, and HTTP server.
"""

import asyncio
import logging
import os
from typing import Optional, Callable, Awaitable
from pathlib import Path

from .session import RadioSession, get_session_manager
from .queue import QueueItem, get_queue_manager
from .transcoder import AudioTranscoder, get_transcoder_pool
from .streaming import StreamingServer, get_streaming_pool
from .scheduler import get_scheduler
from .constants import (
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_PAUSED,
    QUEUE_STATUS_PLAYING,
    QUEUE_STATUS_PLAYED,
    QUEUE_STATUS_FAILED,
    NOTHING_TO_PLAY_AUDIO,
    TRACK_FETCH_TIMEOUT,
)

logger = logging.getLogger(__name__)


class RadioEngine:
    """
    Orchestrates the entire radio streaming pipeline.
    Coordinates session, queue, transcoder, and streaming server.
    """
    
    _instance: Optional["RadioEngine"] = None
    
    def __init__(self):
        self._active_tasks: dict[str, asyncio.Task] = {}  # session_id -> streaming task
        self._session_manager = get_session_manager()
        self._queue_manager = get_queue_manager()
        self._transcoder_pool = get_transcoder_pool()
        self._streaming_pool = get_streaming_pool()
        self._scheduler = get_scheduler()
        self._download_callback: Optional[Callable[[str, str], Awaitable[Optional[str]]]] = None
    
    @classmethod
    def get_instance(cls) -> "RadioEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def set_download_callback(self, callback: Callable[[str, str], Awaitable[Optional[str]]]):
        """
        Set the callback for downloading tracks.
        Callback takes (track_isrc, track_name) and returns file path or None.
        """
        self._download_callback = callback
    
    async def start_streaming(self, session_id: str) -> bool:
        """
        Start streaming for a session.
        Gets the first track and begins the streaming loop.
        """
        session = await self._session_manager.get_session(session_id)
        if not session:
            logger.error(f"Cannot start streaming: session {session_id} not found")
            return False
        
        # Create and start HTTP streaming server
        server = self._streaming_pool.get_or_create(session_id, session.stream_port)
        try:
            await server.start()
            logger.info(f"Streaming server started on port {session.stream_port}")
        except Exception as e:
            logger.error(f"Failed to start streaming server: {e}")
            return False
        
        # Start the streaming loop as a background task
        task = asyncio.create_task(self._streaming_loop(session_id))
        self._active_tasks[session_id] = task
        
        logger.info(f"Started streaming for session {session_id}")
        return True
    
    async def _streaming_loop(self, session_id: str):
        """
        Main streaming loop. Plays tracks one after another.
        Handles track transitions, empty queue, and session termination.
        """
        try:
            while True:
                session = await self._session_manager.get_session(session_id)
                if not session or session.status not in (SESSION_STATUS_ACTIVE, SESSION_STATUS_PAUSED):
                    logger.info(f"Session {session_id} no longer active, stopping stream loop")
                    break
                
                # Handle paused state
                if session.status == SESSION_STATUS_PAUSED:
                    await asyncio.sleep(0.5)
                    continue
                
                # Get next track to play
                next_track = await self._queue_manager.get_next_track(
                    session_id, 
                    repeat=session.repeat_enabled
                )
                
                if not next_track:
                    # Queue is empty - handle empty queue scenario
                    await self._handle_empty_queue(session_id, session.user_id)
                    break
                
                # Play the track
                await self._play_track(session_id, next_track)
                
                # Small delay between tracks for smooth transition
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info(f"Streaming loop cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in streaming loop for session {session_id}: {e}")
        finally:
            # Cleanup when loop exits
            await self._cleanup_session_resources(session_id)
    
    async def _play_track(self, session_id: str, track: QueueItem):
        """Play a single track: download if needed, transcode, and stream."""
        logger.info(f"Playing track: {track.display_name()}")
        
        session = await self._session_manager.get_session(session_id)
        if not session:
            return
        
        # Mark track as playing
        await self._queue_manager.mark_track_playing(session_id, track.position)
        await self._session_manager.set_current_track(session_id, track.position)
        
        # Get file path (download if not cached)
        file_path = track.file_path
        if not file_path or not os.path.exists(file_path):
            file_path = await self._download_track(track)
            if file_path:
                await self._queue_manager.set_track_file_path(session_id, track.position, file_path)
        
        if not file_path or not os.path.exists(file_path):
            logger.error(f"Failed to get file for track: {track.display_name()}")
            await self._queue_manager.mark_track_failed(session_id, track.position)
            # Notify user about failure
            await self._scheduler._notify_user(
                session.user_id,
                f"❌ Failed to play: {track.display_name()}\nSkipping to next track..."
            )
            return
        
        # Get transcoder and streaming server
        transcoder = self._transcoder_pool.get_or_create(session_id, session.bitrate)
        server = self._streaming_pool.get(session_id)
        
        if not server:
            logger.error(f"No streaming server for session {session_id}")
            return
        
        # Stream the track
        try:
            async for chunk in transcoder.start_track(file_path):
                # Check if session is still active
                current_session = await self._session_manager.get_session(session_id)
                if not current_session or current_session.status not in (SESSION_STATUS_ACTIVE, SESSION_STATUS_PAUSED):
                    break
                
                # Handle pause
                while current_session and current_session.status == SESSION_STATUS_PAUSED:
                    await asyncio.sleep(0.1)
                    current_session = await self._session_manager.get_session(session_id)
                
                # Send chunk to streaming server
                await server.write_audio(chunk)
                
                # Update playback position
                position = transcoder.get_current_position()
                await self._session_manager.update_playback_position(
                    session_id, position, duration_added=0
                )
            
            # Track finished - mark as played
            await self._queue_manager.mark_track_played(session_id, track.position)
            
            # Update total duration
            await self._session_manager.update_playback_position(
                session_id, 0, duration_added=track.duration
            )
            
            logger.info(f"Finished playing: {track.display_name()}")
            
            # Check if this was the last track
            if await self._queue_manager.is_last_track(session_id) and not session.repeat_enabled:
                await self._scheduler.notify_last_track(session_id, session.user_id, track.display_name())
            
        except Exception as e:
            logger.error(f"Error streaming track {track.display_name()}: {e}")
            await self._queue_manager.mark_track_failed(session_id, track.position)
    
    async def _download_track(self, track: QueueItem) -> Optional[str]:
        """Download a track using the configured callback."""
        if not self._download_callback:
            logger.warning("No download callback configured")
            return None
        
        try:
            logger.info(f"Downloading track: {track.display_name()}")
            file_path = await asyncio.wait_for(
                self._download_callback(track.track_isrc, track.track_name),
                timeout=TRACK_FETCH_TIMEOUT
            )
            return file_path
        except asyncio.TimeoutError:
            logger.error(f"Download timeout for track: {track.display_name()}")
            return None
        except Exception as e:
            logger.error(f"Download error for track {track.display_name()}: {e}")
            return None
    
    async def _handle_empty_queue(self, session_id: str, user_id: int):
        """Handle empty queue - play nothing to play audio and stop session."""
        logger.info(f"Queue empty for session {session_id}")
        
        # Try to play "nothing to play" audio if it exists
        nothing_audio = Path(__file__).parent.parent / NOTHING_TO_PLAY_AUDIO
        if nothing_audio.exists():
            transcoder = self._transcoder_pool.get_or_create(session_id)
            server = self._streaming_pool.get(session_id)
            
            if server:
                try:
                    async for chunk in transcoder.start_track(str(nothing_audio)):
                        await server.write_audio(chunk)
                except Exception as e:
                    logger.warning(f"Could not play nothing to play audio: {e}")
        
        # Notify user
        await self._scheduler.notify_empty_queue(session_id, user_id)
        
        # Stop the session
        await self.stop_session(session_id, reason="empty_queue")
    
    async def skip_track(self, session_id: str) -> bool:
        """
        Skip the current track and move to the next.
        Returns True if skip was successful.
        """
        session = await self._session_manager.get_session(session_id)
        if not session:
            return False
        
        # Get current track
        current = await self._queue_manager.get_current_track(session_id)
        if current:
            await self._queue_manager.mark_track_skipped(session_id, current.position)
        
        # Stop the current transcoder (this will cause _play_track to exit)
        await self._transcoder_pool.stop_transcoder(session_id)
        
        logger.info(f"Skipped track in session {session_id}")
        return True
    
    async def stop_session(self, session_id: str, reason: str = "user_request"):
        """Stop streaming and clean up a session."""
        logger.info(f"Stopping session {session_id}: {reason}")
        
        # Cancel the streaming task
        if session_id in self._active_tasks:
            self._active_tasks[session_id].cancel()
            try:
                await self._active_tasks[session_id]
            except asyncio.CancelledError:
                pass
            del self._active_tasks[session_id]
        
        # Cleanup resources
        await self._cleanup_session_resources(session_id)
        
        # Stop the session in manager
        session = await self._session_manager.get_session(session_id)
        if session:
            await self._scheduler.notify_session_stopped(session_id, session.user_id, reason)
        
        await self._session_manager.stop_session(session_id, reason)
    
    async def _cleanup_session_resources(self, session_id: str):
        """Clean up all resources for a session."""
        # Stop transcoder
        await self._transcoder_pool.stop_transcoder(session_id)
        
        # Stop streaming server
        await self._streaming_pool.stop_server(session_id)
        
        # Cancel scheduled tasks
        await self._scheduler.cancel_all(session_id)
        
        # Clean up queue
        await self._queue_manager.cleanup_session(session_id)
        
        logger.info(f"Cleaned up resources for session {session_id}")
    
    async def pause_session(self, session_id: str) -> bool:
        """Pause streaming (audio continues but new chunks stop)."""
        session = await self._session_manager.get_session(session_id)
        if not session or session.status != SESSION_STATUS_ACTIVE:
            return False
        
        await self._session_manager.pause_session(session_id)
        return True
    
    async def resume_session(self, session_id: str) -> bool:
        """Resume paused streaming."""
        session = await self._session_manager.get_session(session_id)
        if not session or session.status != SESSION_STATUS_PAUSED:
            return False
        
        await self._session_manager.resume_session(session_id)
        return True
    
    async def shutdown_all(self):
        """Stop all active streaming sessions."""
        for session_id in list(self._active_tasks.keys()):
            await self.stop_session(session_id, reason="shutdown")
        
        await self._transcoder_pool.stop_all()
        await self._streaming_pool.stop_all()
        await self._scheduler.cleanup()
        
        logger.info("All radio sessions shut down")


def get_radio_engine() -> RadioEngine:
    """Get the global radio engine instance."""
    return RadioEngine.get_instance()
