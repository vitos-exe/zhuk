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

Set your Spotify API credentials as environment variables:

```bash
export SPOTIPY_CLIENT_ID=your_spotify_client_id
export SPOTIPY_REDIRECT_URI=your_spotify_redirect_uri
```

Or pass the client ID directly via the CLI:

```bash
zhuk --client-id your_spotify_client_id --redirect-uri your_redirect_uri download <url>
```

You can create a free Spotify application at <https://developer.spotify.com/dashboard>.

## Usage

```
zhuk download <spotify-url> [--output DIR] [--jobs N]
zhuk sync [--output DIR] [--select | --all | --playlist NAME]
```

Tracks already present in the target directory are skipped, and downloads run four at a
time by default (`--jobs`).

### Download a single track

```bash
zhuk download https://open.spotify.com/track/4u7EnebtmKWzUH433cf5Qv
```

### Download an entire playlist

```bash
zhuk download https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
```

### Save to a custom directory

```bash
zhuk download https://open.spotify.com/track/4u7EnebtmKWzUH433cf5Qv --output ~/Music
```

MP3 files are saved to the `downloads/` directory by default.

## Syncing playlists to a device

`zhuk sync` is built for keeping a DJ library in step with Spotify. It lists the playlists on
your account, lets you pick them interactively (type to search, space to toggle), and mirrors
each one into its own subfolder of the target directory.

```bash
zhuk sync --output /Volumes/USB/Music
```

The first run opens the picker and remembers your choice in `<output>/.zhuk.json`. Later runs
need no interaction:

```bash
zhuk sync --output /Volumes/USB/Music          # sync the same playlists again
zhuk sync --output /Volumes/USB/Music --select # change the selection
zhuk sync --output /Volumes/USB/Music --all    # sync every playlist
zhuk sync --output /Volumes/USB/Music --playlist "Deep House" --playlist Techno
```

Each playlist folder also gets an `.m3u8` file listing the tracks in Spotify order, using
relative paths so the folder keeps working after you copy it to a USB stick. Pass
`--no-playlist-file` to skip it.

### Sync deletes local files

**`zhuk sync` is a mirror, not a one-way download.** Any file in a playlist subfolder that is
not currently in that playlist is deleted, including files that are not MP3s. Dotfiles and
`.m3u8` files are never touched.

Tracks are identified by a Spotify track ID embedded in each MP3 on download. Files downloaded
by older versions of `zhuk` do not carry that ID, so **the first sync of an existing library
treats them as unknown and re-downloads everything.**

Three safeguards apply before anything is removed:

- The full list of files to be deleted is printed and you must confirm. Use `--yes` to skip the
  prompt in scripts.
- If a sync would delete 80% or more of a folder, it refuses outright and skips that playlist.
  That usually means a wrong `--output` path or an empty API response. Use `--force` to
  override.
- `--dry-run` reports everything that would change without touching a single file.

Start with `--dry-run` the first time you point `zhuk sync` at a real library.

## How it works

1. **Spotify metadata** – `spotipy` calls the Spotify Web API using a PKCE auth flow (opens a browser on first run) to retrieve the track title and primary artist name.
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

1. Bump the `version` field in `pyproject.toml`, commit, and push to `main`.
2. Tag the release and push the tag:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
3. The *Publish to PyPI* workflow triggers on the tag and uploads the built distributions to PyPI.
