"""
Audio Transcoder
FFmpeg wrapper for converting audio files to MP3 stream.
"""

import asyncio
import logging
import os
from typing import AsyncGenerator, Optional

from .constants import (
    DEFAULT_BITRATE,
    SAMPLE_RATE,
    AUDIO_CHANNELS,
    CHUNK_SIZE,
    FFMPEG_START_TIMEOUT,
)

logger = logging.getLogger(__name__)


class AudioTranscoder:
    """
    Wraps FFmpeg to transcode audio files to MP3 stream.
    Yields chunks of MP3 data for streaming.
    """
    
    def __init__(self, bitrate: int = DEFAULT_BITRATE):
        self.bitrate = bitrate
        self._process: Optional[asyncio.subprocess.Process] = None
        self._current_file: Optional[str] = None
        self._bytes_produced: int = 0
        self._is_running: bool = False
    
    def _build_ffmpeg_cmd(self, input_path: str) -> list:
        """Build FFmpeg command for transcoding to MP3 stream."""
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",                    # No video
            "-acodec", "libmp3lame",  # MP3 codec
            "-b:a", f"{self.bitrate}k",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(AUDIO_CHANNELS),
            "-f", "mp3",              # Output format
            "pipe:1"                  # Output to stdout
        ]
    
    async def start_track(self, file_path: str) -> AsyncGenerator[bytes, None]:
        """
        Start transcoding a track and yield audio chunks.
        
        Args:
            file_path: Path to the audio file (FLAC, MP3, M4A, WAV, etc.)
            
        Yields:
            bytes: Chunks of MP3 data
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        # Stop any existing process
        await self.stop()
        
        self._current_file = file_path
        self._bytes_produced = 0
        self._is_running = True
        
        cmd = self._build_ffmpeg_cmd(file_path)
        logger.info(f"Starting FFmpeg: {' '.join(cmd)}")
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Read and yield chunks
            while self._is_running and self._process.stdout:
                try:
                    chunk = await asyncio.wait_for(
                        self._process.stdout.read(CHUNK_SIZE),
                        timeout=FFMPEG_START_TIMEOUT
                    )
                    
                    if not chunk:
                        # EOF - track finished
                        break
                    
                    self._bytes_produced += len(chunk)
                    yield chunk
                    
                except asyncio.TimeoutError:
                    logger.error("FFmpeg timeout - no output")
                    break
            
            # Wait for process to finish
            await self._process.wait()
            
            # Check for errors
            if self._process.returncode != 0 and self._process.returncode is not None:
                stderr = await self._process.stderr.read() if self._process.stderr else b""
                logger.error(f"FFmpeg error (exit {self._process.returncode}): {stderr.decode()}")
            
        except Exception as e:
            logger.error(f"FFmpeg exception: {e}")
            raise
        finally:
            self._is_running = False
            self._process = None
            logger.info(f"Finished transcoding, produced {self._bytes_produced} bytes")
    
    async def stop(self):
        """Stop the current transcoding process."""
        self._is_running = False
        
        if self._process:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass  # Process already finished
            except Exception as e:
                logger.warning(f"Error stopping FFmpeg: {e}")
            finally:
                self._process = None
        
        logger.info("Transcoder stopped")
    
    def get_current_position(self) -> float:
        """
        Estimate current playback position in seconds.
        Based on bytes produced and bitrate.
        """
        if self._bytes_produced == 0:
            return 0.0
        
        # MP3 bitrate is in kbps, convert to bytes per second
        bytes_per_second = (self.bitrate * 1000) / 8
        return self._bytes_produced / bytes_per_second
    
    def get_bytes_produced(self) -> int:
        """Get total bytes produced so far."""
        return self._bytes_produced
    
    @property
    def is_running(self) -> bool:
        """Check if transcoder is currently running."""
        return self._is_running
    
    @property
    def current_file(self) -> Optional[str]:
        """Get the currently transcoding file."""
        return self._current_file


class TranscoderPool:
    """
    Manages multiple transcoders for different sessions.
    """
    
    _instance: Optional["TranscoderPool"] = None
    
    def __init__(self):
        self._transcoders: dict[str, AudioTranscoder] = {}
    
    @classmethod
    def get_instance(cls) -> "TranscoderPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_or_create(self, session_id: str, bitrate: int = DEFAULT_BITRATE) -> AudioTranscoder:
        """Get or create a transcoder for a session."""
        if session_id not in self._transcoders:
            self._transcoders[session_id] = AudioTranscoder(bitrate)
        return self._transcoders[session_id]
    
    async def stop_transcoder(self, session_id: str):
        """Stop and remove transcoder for a session."""
        if session_id in self._transcoders:
            await self._transcoders[session_id].stop()
            del self._transcoders[session_id]
    
    async def stop_all(self):
        """Stop all transcoders."""
        for transcoder in self._transcoders.values():
            await transcoder.stop()
        self._transcoders.clear()


def get_transcoder_pool() -> TranscoderPool:
    """Get the global transcoder pool."""
    return TranscoderPool.get_instance()
