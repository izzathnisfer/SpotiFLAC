# SpotiFLAC Telegram Bot

Telegram bot frontend for SpotiFLAC with 2GB file upload support via Pyrogram MTProto.

## Features

- 🎵 Download tracks/albums/playlists from Spotify → FLAC
- 📦 File caching via Telegram channel (instant re-downloads)
- 📊 Real-time progress updates
- 🎤 Lyrics download
- 🖼️ Cover art download
- 🔍 Platform availability check
- ⚙️ User settings

## Setup

### 1. Get Telegram Credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in and create an app
3. Copy your `API_ID` and `API_HASH`
4. Create a bot via [@BotFather](https://t.me/BotFather) and get `BOT_TOKEN`
5. Create a private channel for file caching, add the bot as admin, get channel ID

### 2. Install Dependencies

```bash
cd bot
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 4. Install FFmpeg

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Or run the setup script
./scripts/setup.sh
```

### 5. Start the Bot

```bash
# Terminal 1: Start Go backend API
cd .. && go run ./cmd/api

# Terminal 2: Start Telegram bot
cd bot && python main.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and quick guide |
| `/help` | Show all commands |
| `/settings` | Configure bot settings |
| `/queue` | View download queue |
| `/cancel` | Cancel downloads |
| `/lyrics <url>` | Download lyrics only |
| `/cover <url>` | Download cover art |
| `/check <url>` | Check platform availability |

**Or just send a Spotify URL!**

## Architecture

```
User → Pyrogram Bot (Python) → HTTP API → Go Backend
                ↓
        Telegram Cache Channel (file storage)
                ↓
            SQLite DB (file_id mapping)
```

## License

For educational and private use only.
