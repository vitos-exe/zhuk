"""Spotify API helpers for retrieving track and playlist metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()


@dataclass
class TrackInfo:
    """Minimal information about a Spotify track needed to find it on YouTube."""

    title: str
    artist: str

    def search_query(self) -> str:
        """Return a YouTube search query for this track."""
        return f"{self.artist} - {self.title}"


def _build_client() -> spotipy.Spotify:
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    auth_manager = SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_track(url: str) -> TrackInfo:
    """Return :class:`TrackInfo` for a Spotify track URL."""
    sp = _build_client()
    data = sp.track(url)
    title = data["name"]
    artist = data["artists"][0]["name"]
    return TrackInfo(title=title, artist=artist)


def get_playlist(url: str) -> list[TrackInfo]:
    """Return a list of :class:`TrackInfo` for every track in a Spotify playlist."""
    sp = _build_client()
    tracks: list[TrackInfo] = []

    results = sp.playlist_tracks(url)
    while results:
        for item in results["items"]:
            track = item.get("track")
            if track is None:
                continue
            title = track["name"]
            artist = track["artists"][0]["name"]
            tracks.append(TrackInfo(title=title, artist=artist))
        results = sp.next(results) if results.get("next") else None

    return tracks
