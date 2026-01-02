# SpotiFLAC Telegram Bot

A Telegram bot frontend for SpotiFLAC - download Spotify tracks in FLAC quality via Telegram with **2GB file support**.

## Features

- 🎵 **Download tracks** from Spotify URLs (FLAC quality from Tidal/Qobuz/Amazon)
- 💿 **Albums & Playlists** with track selection
- 🔍 **Search** Spotify directly (`/search`)
- 🎤 **Lyrics** download (.lrc files)
- 🖼️ **Cover art** download
- ⚡ **Cache system** - instant re-download via Telegram channel
- 📊 **2GB uploads** using Pyrogram MTProto API
- 👥 **Multi-user** with access control

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/search <query>` | Search Spotify |
| `/settings` | Configure quality & source |
| `/lyrics <url>` | Download lyrics |
| `/cover <url>` | Download cover art |
| `/check <url>` | Check platform availability |
| `/queue` | View download queue |
| `/cancel` | Cancel downloads |
| `/ping` | Health check |

Or just **paste a Spotify URL** directly!

---

## 🆕 New Server Setup

### Prerequisites

- Ubuntu 22.04+ (AWS t3.micro works)
- Git, Go 1.21+, Python 3.11+, FFmpeg

### Step 1: Clone Repository

```bash
cd ~
mkdir -p Projects && cd Projects
git clone -b telegram-bot https://github.com/izzathnisfer/SpotiFLAC.git
cd SpotiFLAC
```

### Step 2: Install Dependencies

```bash
# Install Go
wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Install FFmpeg
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv

# Create Python virtual environment
cd bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Get Telegram Credentials

1. **API_ID & API_HASH**: Go to [my.telegram.org](https://my.telegram.org) → API development tools
2. **BOT_TOKEN**: Message [@BotFather](https://t.me/BotFather) → `/newbot`
3. **CACHE_CHANNEL_ID**: 
   - Create a private channel
   - Add your bot as admin (with post permission)
   - Forward a message from the channel to [@userinfobot](https://t.me/userinfobot) to get the ID

### Step 4: Configure

```bash
cd ~/Projects/SpotiFLAC/bot
cp .env.example .env
nano .env
```

Fill in:
```env
API_ID=123456
API_HASH=abcdef1234567890
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
CACHE_CHANNEL_ID=-1001234567890
ALLOWED_USERS=123456789,987654321
```

### Step 5: Install as Service

```bash
cd ~/Projects/SpotiFLAC
chmod +x scripts/install-services.sh
sudo ./scripts/install-services.sh
```

✅ Done! Bot is now running in background.

---

## 🔄 Already Setup Server

### Pull Latest Changes

```bash
cd ~/Projects/SpotiFLAC
git pull
```

### Restart Services

```bash
sudo systemctl restart spotiflac-api spotiflac-bot
```

### View Logs

```bash
# Bot logs
sudo journalctl -u spotiflac-bot -f

# API logs
sudo journalctl -u spotiflac-api -f
```

---

## Service Commands

| Command | Description |
|---------|-------------|
| `sudo systemctl start spotiflac-bot spotiflac-api` | Start both |
| `sudo systemctl stop spotiflac-bot spotiflac-api` | Stop both |
| `sudo systemctl restart spotiflac-bot` | Restart bot |
| `sudo systemctl status spotiflac-bot` | Check status |
| `sudo journalctl -u spotiflac-bot -f` | Live logs |
| `sudo journalctl -u spotiflac-bot -n 100` | Last 100 lines |

---

## Manual Run (Development)

If you prefer running without systemd:

```bash
cd ~/Projects/SpotiFLAC
./scripts/start.sh
```

Or run separately:
```bash
# Terminal 1: API Server
go run ./cmd/api

# Terminal 2: Bot
cd bot
source venv/bin/activate
python main.py
```

---

## File Structure

```
SpotiFLAC/
├── bot/                    # Telegram bot (Python/Pyrogram)
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration
│   ├── handlers/          # Command handlers
│   │   ├── download.py    # URL detection & downloads
│   │   ├── search.py      # /search command
│   │   ├── settings.py    # /settings command
│   │   └── ...
│   ├── services/
│   │   ├── database.py    # SQLite for cache
│   │   └── backend.py     # HTTP client for Go API
│   └── .env               # Credentials (create from .env.example)
├── cmd/api/main.go        # Go HTTP API server
├── backend/               # Go backend (Tidal/Qobuz/Amazon downloaders)
└── scripts/
    ├── start.sh           # Manual start script
    ├── install-services.sh # Systemd installer
    └── *.service          # Systemd service files
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `CACHE_CHANNEL_ID` | ✅ | Private channel ID for file cache |
| `ALLOWED_USERS` | ❌ | Comma-separated user IDs (empty = allow all) |
| `BACKEND_URL` | ❌ | API URL (default: http://localhost:8765) |
| `LOG_LEVEL` | ❌ | DEBUG, INFO, WARNING, ERROR |

---

## Troubleshooting

### Bot not responding
```bash
sudo systemctl status spotiflac-bot
sudo journalctl -u spotiflac-bot -n 50
```

### "Peer id invalid" error
- Make sure your bot is added as admin to the cache channel
- Verify CACHE_CHANNEL_ID starts with `-100`

### Download fails
```bash
sudo journalctl -u spotiflac-api -f
```
Check if FFmpeg is installed: `ffmpeg -version`

### Restart everything
```bash
sudo systemctl restart spotiflac-api spotiflac-bot
```

---

## Architecture

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │ MTProto (2GB files!)
         ▼
┌─────────────────┐
│  Pyrogram Bot   │ ← Python
│  (port: -)      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Go API Server  │ ← Go
│  (port: 8765)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Tidal / Qobuz   │
│ Amazon Music    │
└─────────────────┘
```

---

## License

Educational use only. Not affiliated with Spotify, Tidal, Qobuz, or Amazon.
