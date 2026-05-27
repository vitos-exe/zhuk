# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --dev          # install all dependencies including dev
uv run pytest tests/ -v              # run all tests
uv run pytest tests/test_spotify.py  # run a single test file
uv run zhuk download <spotify-url>   # run the CLI
```

## Architecture

`zhuk` is a CLI tool that downloads Spotify tracks/playlists as MP3 files from YouTube. Data flows in one direction: Spotify metadata -> YouTube search -> MP3 with embedded ID3 tags.

**Modules:**

- `spotify.py` - Wraps `spotipy` with PKCE auth. Produces `TrackInfo` dataclasses (title, artist, album) from Spotify track or playlist URLs. `build_client()` reads `SPOTIPY_CLIENT_ID` from env; a redirect URI must also be configured via `SPOTIPY_REDIRECT_URI`.
- `downloader.py` - Takes `TrackInfo`, searches YouTube via `yt-dlp` using `"artist - title"` as the query, downloads best audio, converts to 192 kbps MP3 via FFmpeg post-processor, then writes ID3 tags with `mutagen`.
- `matcher.py` - Fuzzy-matches Spotify tracks against local MP3 files using `rapidfuzz`. Currently not wired into the CLI; intended for playlist sync (finding which tracks are already downloaded).
- `main.py` - Click CLI with a single `download` command. Detects track vs. playlist by URL substring and dispatches to `spotify.py` + `downloader.py`.

**Auth:** Spotify uses the PKCE authorization code flow (`SpotifyPKCE`), which opens a browser for the initial login. The client secret is not required.

**Tests:** All tests mock external calls (`build_client`, `yt_dlp.YoutubeDL`). No real Spotify or YouTube requests are made. Use `pytest-mock` fixtures or `unittest.mock.patch` decorators consistent with existing tests.

**Publishing:** Pushing to `main` triggers `.github/workflows/publish.yml`, which builds and publishes to PyPI using OIDC Trusted Publishing (no stored API tokens).
