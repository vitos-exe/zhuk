# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --dev          # install all dependencies including dev
uv run pytest tests/ -v              # run all tests
uv run pytest tests/test_spotify.py  # run a single test file
uv run zhuk download <spotify-url>   # run the CLI
uv run zhuk sync -o ~/Music          # mirror selected playlists into subfolders
```

## Architecture

`zhuk` is a CLI tool that downloads Spotify tracks/playlists as MP3 files from YouTube. Data flows in one direction: Spotify metadata -> YouTube search -> MP3 with embedded ID3 tags.

Two commands: `download` takes a URL and fills a flat directory; `sync` mirrors selected playlists into one subfolder each and deletes local files that left a playlist.

**Modules:**

- `spotify.py` - Wraps `spotipy` with PKCE auth. Produces `TrackInfo` dataclasses (title, artist, album) from Spotify track or playlist URLs. `build_client()` reads `SPOTIPY_CLIENT_ID` from env; a redirect URI must also be configured via `SPOTIPY_REDIRECT_URI`.
- `downloader.py` - Takes `TrackInfo`, searches YouTube via `yt-dlp` using `"artist - title"` as the query, downloads best audio, converts to 192 kbps MP3 via FFmpeg post-processor, then writes ID3 tags with `mutagen`.
- `matcher.py` - Two independent mechanisms. `find_missing_tracks` fuzzy-matches Spotify tracks against local MP3 tags with `rapidfuzz` and backs `download`'s skip-existing behaviour. `diff_playlist` matches exactly on the `TXXX:SPOTIFY_TRACK_ID` frame and backs `sync`, returning orphans as well as missing tracks; fuzzy matching is deliberately not used there, since a false positive would delete a file.
- `sync.py` - Orchestrates a mirror sync: duplicate-name detection, folder renames, per-playlist diffing, the deletion confirmation and the 80% deletion interlock.
- `state.py` - Reads/writes `<target>/.zhuk.json`, which stores the selected playlists and their folders so re-runs need no interaction and renames can be detected by playlist ID.
- `naming.py` - `sanitize_name` / `track_basename`, the single source of truth for playlist folder names and `Artist - Title.mp3` filenames.
- `playlist_file.py` - Writes the per-folder `.m3u8` using relative paths.
- `picker.py` - `questionary` checkbox prompt for interactive playlist selection.
- `main.py` - Click CLI with `download` and `sync` commands, both registered via `cli.add_command`. `sync` only resolves which playlists to act on; the work lives in `sync.py`.

**Auth:** Spotify uses the PKCE authorization code flow (`SpotifyPKCE`), which opens a browser for the initial login. The client secret is not required.

**Tests:** All tests mock external calls (`build_client`, `yt_dlp.YoutubeDL`). No real Spotify or YouTube requests are made. Use `pytest-mock` fixtures or `unittest.mock.patch` decorators consistent with existing tests. `tests/conftest.py` clears `SPOTIPY_*` env vars for every test (Click reads them via `envvar=`, so real credentials would otherwise leak into CLI assertions) and provides a `make_mp3` factory for stub MP3s carrying real ID3 tags.

**Sync identity:** `sync` decides what a local file is purely from the `TXXX:SPOTIFY_TRACK_ID` ID3 frame written at download time. Anything unidentifiable in a playlist folder is an orphan and gets deleted, so never loosen the deletion allowlist in `matcher.is_protected` or the interlock in `sync.DELETION_RATIO_LIMIT` without deliberate thought.

**Publishing:** Pushing a `v*` tag triggers `.github/workflows/publish.yml`, which builds and publishes to PyPI using OIDC Trusted Publishing (no stored API tokens).
