"""
Radio Streaming Service - FastAPI Routes

HTTP endpoints for audio streaming.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from core.player import get_session, create_session, get_all_sessions, StreamSession
import config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "radio",
        "port": config.RADIO_PORT,
        "max_sessions": config.MAX_SESSIONS,
        "active_sessions": len(get_all_sessions())
    }


@router.get("/stream/{session_id}")
async def stream_audio(session_id: str, request: Request):
    """
    Stream audio for a specific session.
    
    This is the main endpoint that VLC connects to.
    URL format: http://<IP>:8766/stream/<session_id>
    """
    session = get_session(session_id)
    
    if not session:
        # For Phase 1 testing, create a test session with hardcoded audio
        if session_id == "test":
            session = await create_test_session()
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Session {session_id} not found. Start a session via Telegram first."
            )
    
    if not session.is_stream_active():
        raise HTTPException(
            status_code=503,
            detail="Stream is not active. No audio is currently playing."
        )
    
    # Increment listener count
    session.listener_count += 1
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"New listener connected to session {session_id} from {client_ip}")
    
    async def stream_with_cleanup():
        """Generator that cleans up on disconnect."""
        try:
            async for chunk in session.stream_audio():
                yield chunk
        finally:
            # Decrement listener count on disconnect
            session.listener_count = max(0, session.listener_count - 1)
            logger.info(f"Listener disconnected from session {session_id}. Remaining: {session.listener_count}")
    
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
    sessions = get_all_sessions()
    return {
        "count": len(sessions),
        "max": config.MAX_SESSIONS,
        "sessions": [s.get_status() for s in sessions]
    }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get info about a specific session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.get_status()


async def create_test_session() -> StreamSession:
    """
    Create a test session for Phase 1 testing.
    Uses a hardcoded test audio file.
    """
    # Look for any audio file in the audio directory
    audio_files = list(config.AUDIO_DIR.glob("*.mp3")) + \
                  list(config.AUDIO_DIR.glob("*.flac")) + \
                  list(config.AUDIO_DIR.glob("*.m4a"))
    
    # Also check for fallback audio
    if config.FALLBACK_AUDIO.exists():
        audio_files.append(config.FALLBACK_AUDIO)
    
    if not audio_files:
        raise HTTPException(
            status_code=503,
            detail=f"No audio files found. Add files to {config.AUDIO_DIR} or generate the fallback audio."
        )
    
    # Use the first audio file found
    test_file = audio_files[0]
    logger.info(f"Creating test session with file: {test_file}")
    
    # Create session
    session = create_session("test", owner_id=0, owner_username="test")
    
    # Start streaming
    success = await session.start_stream(test_file)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start stream")
    
    return session
