"""Fuzzy matching of Spotify tracks against local MP3 files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import mutagen.id3
from rapidfuzz import fuzz

from zhuk.spotify import TrackInfo


@dataclass
class LocalTrack:
    """Metadata from a local MP3 file."""

    filepath: str
    title: str
    artist: str

    def normalized_string(self) -> str:
        """Return a normalized string for fuzzy matching."""
        return f"{self.artist} - {self.title}".lower().strip()


def scan_mp3_files(directory: Path) -> list[Path]:
    """Return a list of MP3 file paths in the given directory (non-recursive)."""
    if not directory.exists():
        return []

    mp3_files: list[Path] = []
    try:
        for filename in os.listdir(directory):
            if filename.lower().endswith(".mp3"):
                mp3_files.append(directory / filename)
    except (OSError, PermissionError):
        pass

    return mp3_files


def read_id3_tags(filepath: Path) -> LocalTrack | None:
    """Read artist and title from ID3 tags; returns None if unreadable."""
    try:
        tags = mutagen.id3.ID3(filepath)
        title = str(tags.get("TIT2", [""])[0]) if "TIT2" in tags else ""
        artist = str(tags.get("TPE1", [""])[0]) if "TPE1" in tags else ""

        if title and artist:
            return LocalTrack(filepath=str(filepath), title=title, artist=artist)
    except Exception:
        pass

    return None


def match_track(
    spotify_track: TrackInfo, local_tracks: list[LocalTrack], threshold: int = 90
) -> LocalTrack | None:
    """Return the best fuzzy-matched local track, or None if below threshold."""
    if not local_tracks:
        return None

    spotify_str = f"{spotify_track.artist} - {spotify_track.title}".lower().strip()

    best_match = None
    best_score = 0

    for local_track in local_tracks:
        local_str = local_track.normalized_string()
        score = fuzz.ratio(spotify_str, local_str)

        if score > best_score:
            best_score = score
            best_match = local_track

    if best_score >= threshold:
        return best_match

    return None


def find_missing_tracks(
    spotify_tracks: list[TrackInfo], local_dir: Path, threshold: int = 90
) -> tuple[list[TrackInfo], list[tuple[TrackInfo, LocalTrack]]]:
    """Return (missing_tracks, matched_tracks) by fuzzy-matching against local_dir."""
    mp3_files = scan_mp3_files(local_dir)
    local_tracks = [t for f in mp3_files if (t := read_id3_tags(f)) is not None]

    missing_tracks: list[TrackInfo] = []
    matched_tracks: list[tuple[TrackInfo, LocalTrack]] = []

    for spotify_track in spotify_tracks:
        match = match_track(spotify_track, local_tracks, threshold)
        if match:
            matched_tracks.append((spotify_track, match))
        else:
            missing_tracks.append(spotify_track)

    return missing_tracks, matched_tracks


SPOTIFY_ID_DESC = "SPOTIFY_TRACK_ID"

# Files the sync itself produces, or that belong to the OS. Under mirror
# semantics everything else in a playlist folder is a deletion candidate.
PROTECTED_SUFFIXES = (".m3u8",)


def is_protected(path: Path) -> bool:
    """Return True if *path* must never be treated as an orphan."""
    name = path.name
    if name.startswith("."):
        return True
    return name.lower().endswith(PROTECTED_SUFFIXES)


def scan_sync_files(directory: Path) -> list[Path]:
    """Return deletable files in *directory* (non-recursive, protected excluded).

    Directories are never returned: mirror sync deletes files it does not
    recognise, and recursing into unknown folders is not worth the risk.
    """
    if not directory.exists():
        return []

    files: list[Path] = []
    try:
        for filename in sorted(os.listdir(directory)):
            path = directory / filename
            if not path.is_file() or is_protected(path):
                continue
            files.append(path)
    except (OSError, PermissionError):
        pass

    return files


def read_spotify_id(filepath: Path) -> str | None:
    """Read the embedded Spotify track ID from *filepath*, or None."""
    try:
        tags = mutagen.id3.ID3(filepath)
        frame = tags.get(f"TXXX:{SPOTIFY_ID_DESC}")
        if frame is not None and frame.text:
            value = str(frame.text[0]).strip()
            return value or None
    except Exception:
        pass

    return None


def index_by_spotify_id(directory: Path) -> tuple[dict[str, Path], list[Path]]:
    """Index *directory* by embedded Spotify track ID.

    Returns ``(index, unidentified)`` where *unidentified* holds deletable files
    carrying no readable Spotify ID.
    """
    index: dict[str, Path] = {}
    unidentified: list[Path] = []

    for path in scan_sync_files(directory):
        spotify_id = read_spotify_id(path)
        if spotify_id is None:
            unidentified.append(path)
        else:
            index.setdefault(spotify_id, path)

    return index, unidentified


def diff_playlist(
    spotify_tracks: list[TrackInfo], directory: Path
) -> tuple[list[TrackInfo], dict[str, Path], list[Path]]:
    """Compare *spotify_tracks* against *directory* by embedded Spotify ID.

    Returns ``(missing, present, orphans)``: tracks to download, a map of
    Spotify ID to the local file already holding it, and local files that no
    longer belong to the playlist.
    """
    index, unidentified = index_by_spotify_id(directory)

    wanted_ids = {t.spotify_id for t in spotify_tracks if t.spotify_id}

    missing: list[TrackInfo] = []
    present: dict[str, Path] = {}
    for track in spotify_tracks:
        local = index.get(track.spotify_id) if track.spotify_id else None
        if local is None:
            missing.append(track)
        else:
            present[track.spotify_id] = local

    # Files with an ID that is no longer in the playlist, plus every file we
    # cannot identify at all.
    orphans = [path for spotify_id, path in index.items() if spotify_id not in wanted_ids]
    orphans.extend(unidentified)

    return missing, present, sorted(set(orphans))
