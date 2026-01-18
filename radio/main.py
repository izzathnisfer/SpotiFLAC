"""
Radio Streaming Service - Main Entry Point

Phase 1: Basic HTTP Audio Streaming Server
"""

import logging
import sys
import asyncio
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import config
from api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Validate configuration
    errors = config.validate_config()
    if errors:
        logger.warning("Configuration warnings:")
        for error in errors:
            logger.warning(f"  - {error}")
        # Don't exit for Phase 1, just warn
    
    app = FastAPI(
        title="Radio Streaming Service",
        description="Lightweight audio streaming server for VLC",
        version="1.0.0"
    )
    
    # CORS middleware (allow VLC and other clients)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router)
    
    @app.on_event("startup")
    async def startup_event():
        """Run on application startup."""
        logger.info("=" * 50)
        logger.info("🎵 Radio Streaming Service Starting...")
        logger.info("=" * 50)
        logger.info(f"Port: {config.RADIO_PORT}")
        logger.info(f"Max Sessions: {config.MAX_SESSIONS}")
        logger.info(f"Audio Bitrate: {config.AUDIO_BITRATE}kbps")
        logger.info(f"Audio Directory: {config.AUDIO_DIR}")
        
        # Try to get public IP
        try:
            public_ip = config.get_public_ip()
            logger.info(f"Public IP: {public_ip}")
            logger.info(f"Test URL: http://{public_ip}:{config.RADIO_PORT}/stream/test")
        except Exception as e:
            logger.warning(f"Could not determine public IP: {e}")
        
        logger.info("=" * 50)
        logger.info("Open VLC → Media → Open Network Stream")
        logger.info(f"Enter: http://<YOUR_IP>:{config.RADIO_PORT}/stream/test")
        logger.info("=" * 50)
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Run on application shutdown."""
        logger.info("Radio Streaming Service shutting down...")
        
        # Stop all active sessions
        from core.player import get_all_sessions
        for session in get_all_sessions():
            await session.stop()
        
        logger.info("All sessions stopped. Goodbye!")
    
    return app


app = create_app()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════╗
    ║           🎵 Radio Streaming Service 🎵              ║
    ║                  Phase 1 - MVP                       ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.RADIO_PORT,
        reload=False,  # Disable reload for production-like behavior
        log_level=config.LOG_LEVEL.lower()
    )
