"""Fuzzy matching of Spotify tracks against local MP3 files."""

from __future__ import annotations

import os
from dataclasses import dataclass

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


def scan_mp3_files(directory: str) -> list[str]:
    """Return a list of MP3 file paths in the given directory (non-recursive)."""
    if not os.path.exists(directory):
        return []

    mp3_files = []
    try:
        for filename in os.listdir(directory):
            if filename.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(directory, filename))
    except (OSError, PermissionError):
        pass

    return mp3_files


def read_id3_tags(filepath: str) -> LocalTrack | None:
    """Read artist and title from ID3 tags; returns None if unreadable."""
    try:
        tags = mutagen.id3.ID3(filepath)
        title = str(tags.get("TIT2", [""])[0]) if "TIT2" in tags else ""
        artist = str(tags.get("TPE1", [""])[0]) if "TPE1" in tags else ""

        if title and artist:
            return LocalTrack(filepath=filepath, title=title, artist=artist)
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
    spotify_tracks: list[TrackInfo], local_dir: str, threshold: int = 90
) -> tuple[list[TrackInfo], list[tuple[TrackInfo, LocalTrack]]]:
    """Return (missing_tracks, matched_tracks) by fuzzy-matching against local_dir."""
    mp3_files = scan_mp3_files(local_dir)
    local_tracks = [t for f in mp3_files if (t := read_id3_tags(f)) is not None]

    missing_tracks = []
    matched_tracks = []

    for spotify_track in spotify_tracks:
        match = match_track(spotify_track, local_tracks, threshold)
        if match:
            matched_tracks.append((spotify_track, match))
        else:
            missing_tracks.append(spotify_track)

    return missing_tracks, matched_tracks
