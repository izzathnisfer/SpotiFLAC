# Radio Streaming Service - Assets

This directory contains audio assets used by the Radio service.

## Files

- `no_songs_queue.mp3` - TTS message played when queue is empty

## Generating TTS Audio

Run the script to generate the TTS audio:

```bash
cd /path/to/radio
chmod +x scripts/generate_tts.sh
./scripts/generate_tts.sh
```

Or manually create a 5-second test tone:

```bash
ffmpeg -f lavfi -i "sine=frequency=440:duration=5" -c:a libmp3lame -b:a 128k assets/test_tone.mp3
```
