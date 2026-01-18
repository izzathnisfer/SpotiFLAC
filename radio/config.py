"""
Radio Streaming Service - Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.absolute()

# ============================================
# Telegram Configuration
# ============================================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin user IDs (comma-separated in env)
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

# ============================================
# Radio Server Configuration
# ============================================
RADIO_PORT = int(os.getenv("RADIO_PORT", "8766"))
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "20"))
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "10"))
AUDIO_BITRATE = int(os.getenv("AUDIO_BITRATE", "128"))

# ============================================
# SpotiFLAC Integration
# ============================================
SPOTIFLAC_API_URL = os.getenv("SPOTIFLAC_API_URL", "http://localhost:8765")

# ============================================
# Storage
# ============================================
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", "./audio"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./radio.db"))

# Ensure audio directory exists
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Assets directory
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Fallback audio file
FALLBACK_AUDIO = ASSETS_DIR / "no_songs_queue.mp3"

# ============================================
# Logging
# ============================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def validate_config() -> list[str]:
    """Validate configuration and return list of errors."""
    errors = []
    
    if not API_ID:
        errors.append("API_ID is required")
    if not API_HASH:
        errors.append("API_HASH is required")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required")
    if not ADMIN_IDS:
        errors.append("ADMIN_IDS is required (at least one admin)")
    
    return errors


def get_public_ip() -> str:
    """Get the public IP address of the server."""
    import httpx
    try:
        response = httpx.get("https://api.ipify.org", timeout=5)
        return response.text.strip()
    except Exception:
        try:
            response = httpx.get("https://ifconfig.me", timeout=5)
            return response.text.strip()
        except Exception:
            return "YOUR_SERVER_IP"


def get_stream_url(session_id: str) -> str:
    """Get the full streaming URL for a session."""
    ip = get_public_ip()
    return f"http://{ip}:{RADIO_PORT}/stream/{session_id}"
