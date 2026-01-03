"""
HTTP Streaming Server
Serves audio stream to multiple listeners via HTTP.
"""

import asyncio
import logging
from typing import Optional, Set
from collections import deque

from aiohttp import web

from .constants import (
    MAX_LISTENERS,
    BUFFER_SIZE,
    CHUNK_SIZE,
)

logger = logging.getLogger(__name__)


class RingBuffer:
    """
    Thread-safe circular buffer for audio data.
    Allows writer to push data while readers consume it.
    """
    
    def __init__(self, max_size: int = BUFFER_SIZE):
        self._buffer: deque = deque(maxlen=max_size // CHUNK_SIZE)
        self._lock: Optional[asyncio.Lock] = None
        self._new_data: Optional[asyncio.Event] = None
    
    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    @property
    def new_data(self) -> asyncio.Event:
        if self._new_data is None:
            self._new_data = asyncio.Event()
        return self._new_data
    
    async def write(self, data: bytes):
        """Write data to the buffer."""
        async with self.lock:
            self._buffer.append(data)
            self.new_data.set()
    
    async def read(self, timeout: float = 5.0) -> Optional[bytes]:
        """
        Read data from the buffer.
        Waits for new data if buffer is empty.
        Returns None on timeout.
        """
        try:
            # Wait for data if buffer is empty
            if not self._buffer:
                self.new_data.clear()
                await asyncio.wait_for(self.new_data.wait(), timeout=timeout)
            
            async with self.lock:
                if self._buffer:
                    return self._buffer.popleft()
                return None
        except asyncio.TimeoutError:
            return None
    
    def clear(self):
        """Clear the buffer."""
        self._buffer.clear()
    
    @property
    def size(self) -> int:
        """Get current buffer size in chunks."""
        return len(self._buffer)


class StreamingServer:
    """
    HTTP server that streams audio to connected clients.
    """
    
    def __init__(self, session_id: str, port: int, host: str = "0.0.0.0"):
        self.session_id = session_id
        self.port = port
        self.host = host
        
        self._buffer = RingBuffer()
        self._clients: Set[web.StreamResponse] = set()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._is_running = False
        self._lock: Optional[asyncio.Lock] = None
    
    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def start(self) -> str:
        """
        Start the HTTP streaming server.
        Returns the stream URL.
        """
        self._app = web.Application()
        self._app.router.add_get("/", self._handle_client)
        self._app.router.add_get("/health", self._handle_health)
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        
        self._is_running = True
        logger.info(f"Streaming server started on {self.host}:{self.port}")
        
        return f"http://{self.host}:{self.port}/"
    
    async def stop(self):
        """Stop the streaming server and disconnect all clients."""
        self._is_running = False
        
        # Close all client connections
        async with self.lock:
            for client in list(self._clients):
                try:
                    await client.write_eof()
                except Exception:
                    pass
            self._clients.clear()
        
        # Stop the server
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        self._buffer.clear()
        logger.info(f"Streaming server stopped on port {self.port}")
    
    async def write_audio(self, data: bytes):
        """Write audio data to the buffer and broadcast to clients."""
        await self._buffer.write(data)
        await self._broadcast_chunk(data)
    
    async def _broadcast_chunk(self, chunk: bytes):
        """Broadcast a chunk to all connected clients."""
        async with self.lock:
            disconnected = []
            
            for client in self._clients:
                try:
                    await client.write(chunk)
                except Exception as e:
                    logger.debug(f"Client disconnected: {e}")
                    disconnected.append(client)
            
            # Remove disconnected clients
            for client in disconnected:
                self._clients.discard(client)
    
    async def _handle_client(self, request: web.Request) -> web.StreamResponse:
        """Handle a new client connection."""
        # Check listener limit
        if len(self._clients) >= MAX_LISTENERS:
            logger.warning(f"Max listeners reached ({MAX_LISTENERS})")
            return web.Response(status=503, text="Server full")
        
        # Create streaming response
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "audio/mpeg",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache, no-store",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*",
                "Icy-Name": "SpotiFLAC Radio",
            }
        )
        await response.prepare(request)
        
        # Add to clients set
        async with self.lock:
            self._clients.add(response)
        
        client_ip = request.remote
        logger.info(f"Client connected: {client_ip} (total: {len(self._clients)})")
        
        try:
            # Keep connection alive while server is running
            while self._is_running:
                # Read from buffer and send to this client
                # (Broadcasting is done in write_audio, so we just wait here)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Client error: {e}")
        finally:
            async with self.lock:
                self._clients.discard(response)
            logger.info(f"Client disconnected: {client_ip} (remaining: {len(self._clients)})")
        
        return response
    
    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "session_id": self.session_id,
            "listeners": len(self._clients),
            "max_listeners": MAX_LISTENERS,
        })
    
    def get_listener_count(self) -> int:
        """Get the number of connected listeners."""
        return len(self._clients)
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._is_running


class StreamingServerPool:
    """
    Manages streaming servers for multiple sessions.
    """
    
    _instance: Optional["StreamingServerPool"] = None
    
    def __init__(self):
        self._servers: dict[str, StreamingServer] = {}
    
    @classmethod
    def get_instance(cls) -> "StreamingServerPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_or_create(self, session_id: str, port: int, host: str = "0.0.0.0") -> StreamingServer:
        """Get or create a streaming server for a session."""
        if session_id not in self._servers:
            self._servers[session_id] = StreamingServer(session_id, port, host)
        return self._servers[session_id]
    
    def get(self, session_id: str) -> Optional[StreamingServer]:
        """Get streaming server for a session."""
        return self._servers.get(session_id)
    
    async def stop_server(self, session_id: str):
        """Stop and remove server for a session."""
        if session_id in self._servers:
            await self._servers[session_id].stop()
            del self._servers[session_id]
    
    async def stop_all(self):
        """Stop all streaming servers."""
        for server in self._servers.values():
            await server.stop()
        self._servers.clear()


def get_streaming_pool() -> StreamingServerPool:
    """Get the global streaming server pool."""
    return StreamingServerPool.get_instance()
