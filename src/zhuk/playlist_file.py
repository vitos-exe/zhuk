"""Extended M3U8 playlist generation for synced playlist folders."""

from __future__ import annotations

import os
from pathlib import Path

from zhuk.naming import sanitize_name
from zhuk.spotify import TrackInfo

M3U8_SUFFIX = ".m3u8"


def playlist_file_path(folder: Path, playlist_name: str) -> Path:
    """Return the path of the M3U8 file for *playlist_name* inside *folder*."""
    return Path(folder) / f"{sanitize_name(playlist_name)}{M3U8_SUFFIX}"


def write_m3u8(
    folder: Path,
    playlist_name: str,
    tracks: list[TrackInfo],
    local_paths: dict[str, Path],
) -> Path:
    """Write an M3U8 for *tracks* in Spotify order into *folder*.

    Paths are written relative to *folder* so the directory keeps working after
    being copied to a USB stick. Tracks with no local file are omitted.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = playlist_file_path(folder, playlist_name)

    lines = ["#EXTM3U"]
    for track in tracks:
        local = local_paths.get(track.spotify_id) if track.spotify_id else None
        if local is None:
            continue
        relative = os.path.relpath(Path(local), folder)
        lines.append(f"#EXTINF:-1,{track.artist} - {track.title}")
        lines.append(relative)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
