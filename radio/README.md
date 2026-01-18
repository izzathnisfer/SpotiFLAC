# Radio Streaming Service

A lightweight, multi-user audio streaming server controlled via Telegram Bot.

## Quick Start

### 1. Install Dependencies

```bash
cd radio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Generate Test Audio

```bash
# Create a 10-second test tone
ffmpeg -f lavfi -i "sine=frequency=440:duration=10" -c:a libmp3lame -b:a 128k audio/test.mp3
```

### 4. Run the Server

```bash
python main.py
```

### 5. Test with VLC

Open VLC → Media → Open Network Stream → Enter:
```
http://<YOUR_SERVER_IP>:8766/stream/test
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /stream/<session_id>` | Audio stream (VLC connects here) |
| `GET /sessions` | List all active sessions |
| `GET /session/<session_id>` | Get session info |

## Project Structure

```
radio/
├── main.py          # FastAPI entry point
├── config.py        # Environment configuration
├── requirements.txt # Python dependencies
├── core/
│   └── player.py    # FFmpeg streaming logic
├── api/
│   └── routes.py    # HTTP endpoints
├── audio/           # Audio files storage
└── assets/          # Fallback audio files
```

## License

Educational use only.
