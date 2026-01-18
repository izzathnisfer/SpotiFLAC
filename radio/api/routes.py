"""
Radio Streaming Service - FastAPI Routes (Phase 2)

HTTP endpoints for audio streaming with queue support.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from core.player import get_player, create_player, remove_player, get_all_players, StreamPlayer
from core.queue_manager import Track, get_queue
from core.session_manager import get_session_manager
import config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    players = get_all_players()
    return {
        "status": "ok",
        "service": "radio",
        "port": config.RADIO_PORT,
        "max_sessions": config.MAX_SESSIONS,
        "active_sessions": len(players),
        "total_listeners": sum(p.listener_count for p in players)
    }


@router.get("/stream/{session_id}")
async def stream_audio(session_id: str, request: Request):
    """
    Stream audio for a specific session.
    VLC connects here: http://<IP>:8766/stream/<session_id>
    """
    player = get_player(session_id)
    
    if not player:
        # For backward compatibility with Phase 1 testing
        if session_id == "test":
            player = await create_test_player()
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Session {session_id} not found. Start a session via Telegram first."
            )
    
    # Start the player if not already playing
    if not player.is_playing():
        await player.start()
    
    # Track listener
    player.listener_count += 1
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Listener connected to session {session_id} from {client_ip} (total: {player.listener_count})")
    
    async def stream_with_cleanup():
        """Generator that cleans up on disconnect."""
        try:
            async for chunk in player.stream_audio():
                yield chunk
        finally:
            player.listener_count = max(0, player.listener_count - 1)
            logger.info(f"Listener disconnected from session {session_id}. Remaining: {player.listener_count}")
    
    return StreamingResponse(
        stream_with_cleanup(),
        media_type="audio/aac",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/sessions")
async def list_sessions():
    """List all active sessions (admin endpoint)."""
    players = get_all_players()
    return {
        "count": len(players),
        "max": config.MAX_SESSIONS,
        "total_listeners": sum(p.listener_count for p in players),
        "sessions": [p.get_status() for p in players]
    }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get info about a specific session."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    return player.get_status()


@router.get("/session/{session_id}/queue")
async def get_session_queue(session_id: str):
    """Get the queue for a session."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    return player.queue.to_dict()


@router.post("/session/{session_id}/skip")
async def skip_track(session_id: str):
    """Skip the current track."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await player.skip()
    return {"success": True, "message": "Skipped to next track"}


@router.post("/session/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause the session."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await player.pause()
    return {"success": True, "message": "Paused"}


@router.post("/session/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume the session."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await player.resume()
    return {"success": True, "message": "Resumed"}


@router.delete("/session/{session_id}")
async def stop_session(session_id: str):
    """Stop and remove a session."""
    player = get_player(session_id)
    if not player:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await player.stop()
    remove_player(session_id)
    return {"success": True, "message": "Session stopped"}


async def create_test_player() -> StreamPlayer:
    """Create a test player for Phase 1/2 testing."""
    # Look for any audio file
    audio_files = list(config.AUDIO_DIR.glob("*.mp3")) + \
                  list(config.AUDIO_DIR.glob("*.flac")) + \
                  list(config.AUDIO_DIR.glob("*.m4a"))
    
    if config.FALLBACK_AUDIO.exists():
        audio_files.append(config.FALLBACK_AUDIO)
    
    if not audio_files:
        raise HTTPException(
            status_code=503,
            detail=f"No audio files found in {config.AUDIO_DIR}"
        )
    
    # Create player
    player = create_player("test", owner_id=0)
    
    # Add all audio files to queue
    for i, audio_file in enumerate(audio_files[:5]):  # Max 5 test files
        track = Track(
            id=str(uuid.uuid4())[:8],
            file_path=audio_file,
            title=audio_file.stem,
            artist="Test",
            added_by=0
        )
        await player.add_track(track)
    
    logger.info(f"Created test player with {len(audio_files)} tracks")
    return player
