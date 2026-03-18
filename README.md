# zhuk

A command-line tool that downloads Spotify tracks and playlists as MP3 files from YouTube.

## Requirements

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (build tool and package manager)
- [FFmpeg](https://ffmpeg.org/download.html) installed and on your `PATH` (used by yt-dlp for audio conversion)
- A [Spotify Developer](https://developer.spotify.com/dashboard) application (free) to obtain API credentials

## Installation

```bash
uv sync
```

## Configuration

Copy `.env.example` to `.env` and fill in your Spotify API credentials:

```bash
cp .env.example .env
```

```
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
```

You can create a free Spotify application at <https://developer.spotify.com/dashboard>.

## Usage

```
zhuk <spotify-url> [--output DIR]
```

### Download a single track

```bash
zhuk https://open.spotify.com/track/4u7EnebtmKWzUH433cf5Qv
```

### Download an entire playlist

```bash
zhuk https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
```

### Save to a custom directory

```bash
zhuk https://open.spotify.com/track/4u7EnebtmKWzUH433cf5Qv --output ~/Music
```

MP3 files are saved to the `downloads/` directory by default.

## How it works

1. **Spotify metadata** – `spotipy` calls the Spotify Web API to retrieve the track title and primary artist name (no login required, only client credentials).
2. **YouTube search & download** – `yt-dlp` searches YouTube for `"<artist> - <title>"` and downloads the best audio stream.
3. **MP3 conversion** – `yt-dlp` post-processes the audio with FFmpeg to produce a 192 kbps MP3 file.

## Development

```bash
uv sync --dev
uv run pytest tests/ -v
```
