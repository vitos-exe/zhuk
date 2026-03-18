"""Spotify API helpers for retrieving track and playlist metadata."""

from __future__ import annotations

from dataclasses import dataclass

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


@dataclass
class TrackInfo:
    """Minimal information about a Spotify track needed to find it on YouTube."""

    title: str
    artist: str
    album: str = ""

    def search_query(self) -> str:
        """Return a YouTube search query for this track."""
        return f"{self.artist} - {self.title}"


def build_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(scope=["playlist-read-private", "playlist-read-collaborative"])
    return spotipy.Spotify(auth_manager=auth_manager)


def get_track(url: str) -> TrackInfo | None:
    """Return :class:`TrackInfo` for a Spotify track URL."""
    sp = build_client()
    data = sp.track(url)
    if data is not None:
        title = data["name"]
        artist = data["artists"][0]["name"]
        album = data["album"]["name"]
        return TrackInfo(title=title, artist=artist, album=album)
    return None


def get_playlist(url: str) -> list[TrackInfo]:
    """Return a list of :class:`TrackInfo` for every track in a Spotify playlist."""
    sp = build_client()
    tracks: list[TrackInfo] = []

    results = sp.playlist_tracks(url)
    while results:
        for item in results["items"]:
            track = item.get("item")
            if track is None:
                continue
            title = track["name"]
            artist = track["artists"][0]["name"]
            album = track["album"]["name"]
            tracks.append(TrackInfo(title=title, artist=artist, album=album))
        results = sp.next(results) if results.get("next") else None

    return tracks
