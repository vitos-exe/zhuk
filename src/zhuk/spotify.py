"""Spotify API helpers for retrieving track and playlist metadata."""

from __future__ import annotations

from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyPKCE


@dataclass
class TrackInfo:
    """Minimal information about a Spotify track needed to find it on YouTube."""

    title: str
    artist: str
    album: str = ""

    def search_query(self) -> str:
        """Return a YouTube search query for this track."""
        return f"{self.artist} - {self.title}"


def build_client(client_id: str | None = None, redirect_uri: str | None = None) -> spotipy.Spotify:
    auth_manager = SpotifyPKCE(client_id=client_id, redirect_uri=redirect_uri, scope=["playlist-read-private", "playlist-read-collaborative"])
    return spotipy.Spotify(auth_manager=auth_manager)


def get_track(url: str, client_id: str | None = None, redirect_uri: str | None = None) -> TrackInfo | None:
    """Return :class:`TrackInfo` for a Spotify track URL."""
    sp = build_client(client_id, redirect_uri)
    data = sp.track(url)
    if data is not None:
        title = data["name"]
        artist = data["artists"][0]["name"]
        album = data["album"]["name"]
        return TrackInfo(title=title, artist=artist, album=album)
    return None


def get_playlist(url: str, client_id: str | None = None, redirect_uri: str | None = None) -> list[TrackInfo]:
    """Return a list of :class:`TrackInfo` for every track in a Spotify playlist."""
    sp = build_client(client_id, redirect_uri)
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
