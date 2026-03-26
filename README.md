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
zhuk <spotify-url> [--output DIR] [--sync]
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

### Sync mode - only download missing tracks

Use `--sync` to check what's already in your local directory and only download tracks that aren't present:

```bash
zhuk https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M --output ~/Music --sync
```

In sync mode, zhuk:
- Scans the output directory for existing MP3 files
- Reads ID3 tags (artist and title) from each MP3
- Uses fuzzy matching (90% similarity) to identify which tracks are already present
- Only downloads tracks that aren't found locally

This is useful for keeping playlists up to date without re-downloading everything.

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

## Publishing to PyPI

The repository includes a GitHub Actions workflow (`.github/workflows/publish.yml`) that automatically builds and publishes the package to PyPI on every push to the `main` branch.

### One-time setup: configure a PyPI Trusted Publisher

This workflow uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — no API tokens are stored in GitHub.

1. Log in to <https://pypi.org> and go to your account → *Publishing*.
2. Under **Add a new pending publisher**, fill in:
   - **PyPI project name**: `zhuk`
   - **Owner**: `vitos-exe` (your GitHub user/org)
   - **Repository**: `zhuk`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Save the pending publisher.
4. In your GitHub repository go to **Settings → Environments** and create an environment named **`pypi`**. Add any required protection rules (e.g. require a reviewer before deploying).

### Publishing a new version

1. Bump the `version` field in `pyproject.toml`.
2. Commit and push to `main`.
3. The *Publish to PyPI* workflow will trigger automatically and upload the built distributions to PyPI.
