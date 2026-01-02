"""
SpotiFLAC Telegram Bot Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# Telegram API Configuration
# =============================================================================

API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Cache channel for storing downloaded files
CACHE_CHANNEL_ID: int = int(os.getenv("CACHE_CHANNEL_ID", "0"))

# Allowed users (empty = allow all)
_allowed = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: list[int] = [int(x.strip()) for x in _allowed.split(",") if x.strip()]


# =============================================================================
# Backend Configuration
# =============================================================================

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8765")


# =============================================================================
# Paths
# =============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_PATH = Path(os.getenv("DOWNLOAD_PATH", "/tmp/spotiflac"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "spotiflac.db")))

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Logging
# =============================================================================

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# =============================================================================
# Bot Settings
# =============================================================================

# Progress update throttle (seconds)
PROGRESS_UPDATE_INTERVAL: float = 2.0

# Maximum tracks per page in album/playlist view
TRACKS_PER_PAGE: int = 8


# =============================================================================
# Validation
# =============================================================================

def validate_config() -> list[str]:
    """Validate required configuration. Returns list of errors."""
    errors = []
    
    if not API_ID:
        errors.append("API_ID is required (get from my.telegram.org)")
    if not API_HASH:
        errors.append("API_HASH is required (get from my.telegram.org)")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required (get from @BotFather)")
    if not CACHE_CHANNEL_ID:
        errors.append("CACHE_CHANNEL_ID is required (create a private channel)")
    
    return errors
