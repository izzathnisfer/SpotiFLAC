"""
Unit Test for bot/radio/transcoder.py
"""
import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from radio.transcoder import AudioTranscoder, TranscoderPool, get_transcoder_pool
from radio.constants import DEFAULT_BITRATE, SAMPLE_RATE

class TestAudioTranscoder(unittest.IsolatedAsyncioTestCase):
    def test_build_ffmpeg_cmd(self):
        """Verify FFmpeg command line arguments."""
        transcoder = AudioTranscoder(bitrate=192)
        cmd = transcoder._build_ffmpeg_cmd("/path/to/file.flac")
        
        self.assertIn("ffmpeg", cmd)
        self.assertIn("/path/to/file.flac", cmd)
        self.assertIn("192k", cmd)
        self.assertIn(str(SAMPLE_RATE), cmd)
        self.assertIn("pipe:1", cmd)

    def test_position_calculation(self):
        """Verify playback position estimation based on bytes produced."""
        transcoder = AudioTranscoder(bitrate=128)
        # 128 kbps = 16,000 bytes/second
        # Produce 32,000 bytes -> 2.0 seconds
        transcoder._bytes_produced = 32000
        self.assertEqual(transcoder.get_current_position(), 2.0)

    @patch('asyncio.create_subprocess_exec')
    async def test_start_stop(self, mock_exec):
        """Verify process management logic."""
        mock_process = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process
        
        transcoder = AudioTranscoder()
        
        # We need a real file path for the exists check
        with patch('os.path.exists', return_value=True):
            # start_track is an AsyncGenerator
            gen = transcoder.start_track("dummy.mp3")
            
            # Start the generator to trigger the subprocess call
            try:
                await anext(gen)
            except (StopAsyncIteration, AttributeError): # It's okay if it fails later
                pass
                
            self.assertTrue(transcoder.is_running)
            mock_exec.assert_called_once()
            
            # Stop it
            await transcoder.stop()
            self.assertFalse(transcoder.is_running)
            mock_process.terminate.assert_called_once()

class TestTranscoderPool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        TranscoderPool._instance = None
        self.pool = get_transcoder_pool()

    async def test_singleton(self):
        self.assertEqual(self.pool, get_transcoder_pool())

    async def test_pool_management(self):
        t1 = self.pool.get_or_create("s1", 128)
        self.assertEqual(t1.bitrate, 128)
        self.assertEqual(self.pool.get_or_create("s1"), t1)
        
        with patch.object(t1, 'stop', new_callable=AsyncMock) as mock_stop:
            await self.pool.stop_transcoder("s1")
            mock_stop.assert_called_once()

if __name__ == "__main__":
    unittest.main()
