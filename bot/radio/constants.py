"""
Radio Streaming Constants
All configuration values for the radio streaming feature.
"""

# =============================================================================
# Session Limits
# =============================================================================

# Maximum session duration in seconds (6 hours)
MAX_SESSION_DURATION = 6 * 60 * 60  # 21600 seconds

# Default session duration in seconds (30 minutes)
DEFAULT_SESSION_DURATION = 30 * 60  # 1800 seconds

# Warning threshold - notify user at 5 hours (1 hour before max)
WARNING_THRESHOLD = 5 * 60 * 60  # 18000 seconds

# Maximum concurrent listeners per session
MAX_LISTENERS = 8

# =============================================================================
# Streaming Configuration
# =============================================================================

# Default audio bitrate (kbps)
DEFAULT_BITRATE = 128

# High quality bitrate (kbps)
HIGH_BITRATE = 320

# Audio sample rate (Hz)
SAMPLE_RATE = 44100

# Number of audio channels (stereo)
AUDIO_CHANNELS = 2

# Port range for streaming servers
STREAM_PORT_START = 8100
STREAM_PORT_END = 8199
STREAM_PORT_RANGE = (STREAM_PORT_START, STREAM_PORT_END)

# =============================================================================
# Buffer Configuration
# =============================================================================

# Ring buffer size in bytes (64KB)
BUFFER_SIZE = 64 * 1024

# Chunk size for streaming (4KB)
CHUNK_SIZE = 4 * 1024

# =============================================================================
# Timeouts
# =============================================================================

# Idle timeout - stop session if no activity (5 minutes)
IDLE_TIMEOUT = 5 * 60

# Timeout for downloading/fetching a track (2 minutes)
TRACK_FETCH_TIMEOUT = 120

# Timeout for FFmpeg to start producing output (30 seconds)
FFMPEG_START_TIMEOUT = 30

# =============================================================================
# Paths
# =============================================================================

# Path to "nothing to play" audio file (relative to bot directory)
NOTHING_TO_PLAY_AUDIO = "assets/Nothing more to play - The server will stop now.wav"

# =============================================================================
# Status Constants
# =============================================================================

# Session statuses
SESSION_STATUS_ACTIVE = "active"
SESSION_STATUS_PAUSED = "paused"
SESSION_STATUS_STOPPED = "stopped"

# Queue item statuses
QUEUE_STATUS_PENDING = "pending"
QUEUE_STATUS_PLAYING = "playing"
QUEUE_STATUS_PLAYED = "played"
QUEUE_STATUS_SKIPPED = "skipped"
QUEUE_STATUS_FAILED = "failed"

# =============================================================================
# Event Types (for logging)
# =============================================================================

EVENT_SESSION_START = "session_start"
EVENT_SESSION_STOP = "session_stop"
EVENT_SESSION_PAUSE = "session_pause"
EVENT_SESSION_RESUME = "session_resume"
EVENT_TRACK_ADD = "track_add"
EVENT_TRACK_REMOVE = "track_remove"
EVENT_TRACK_PLAY = "track_play"
EVENT_TRACK_SKIP = "track_skip"
EVENT_TRACK_ERROR = "track_error"
EVENT_LISTENER_JOIN = "listener_join"
EVENT_LISTENER_LEAVE = "listener_leave"
EVENT_ERROR = "error"
