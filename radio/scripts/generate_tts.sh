#!/bin/bash
# Generate TTS audio for fallback message
# Run this on the server to create the "No Songs in Queue" audio

# Install required tools if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
fi

# Check for espeak (text-to-speech)
if ! command -v espeak &> /dev/null; then
    echo "Installing espeak..."
    sudo apt-get install -y espeak
fi

# Create assets directory
mkdir -p assets

# Generate TTS audio using espeak
# Message: "No songs in queue. Add songs to play and enjoy your radio."
echo "Generating TTS audio..."

# Generate WAV first, then convert to MP3
espeak -v en-us -s 140 -p 50 \
    "No songs in queue. Add songs to play and enjoy your radio." \
    --stdout | ffmpeg -y -i pipe:0 -c:a libmp3lame -b:a 128k assets/no_songs_queue.mp3

if [ -f "assets/no_songs_queue.mp3" ]; then
    echo "✅ Generated assets/no_songs_queue.mp3"
    ls -la assets/no_songs_queue.mp3
else
    echo "❌ Failed to generate audio. Creating silent placeholder..."
    # Create 5 seconds of silence as fallback
    ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 5 -c:a libmp3lame -b:a 128k assets/no_songs_queue.mp3
fi

echo "Done!"
