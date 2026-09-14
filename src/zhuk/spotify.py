"""Spotify API helpers for retrieving track and playlist metadata."""

from __future__ import annotations

from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyPKCE

SCOPES = ["playlist-read-private", "playlist-read-collaborative"]


@dataclass
class TrackInfo:
    """Minimal information about a Spotify track needed to find it on YouTube."""

    title: str
    artist: str
    album: str = ""
    spotify_id: str = ""
    isrc: str = ""

    def search_query(self) -> str:
        """Return a YouTube search query for this track."""
        return f"{self.artist} - {self.title}"


@dataclass
class PlaylistInfo:
    """A playlist belonging to the authenticated user."""

    id: str
    name: str
    track_count: int = 0


def build_client(client_id: str | None = None, redirect_uri: str | None = None) -> spotipy.Spotify:
    auth_manager = SpotifyPKCE(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=SCOPES,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _track_info(track: dict) -> TrackInfo | None:
    """Build :class:`TrackInfo` from a Spotify track object."""
    if not track:
        return None

    artists = track.get("artists") or []
    external_ids = track.get("external_ids") or {}
    album = track.get("album") or {}

    return TrackInfo(
        title=track.get("name") or "",
        artist=artists[0]["name"] if artists else "",
        album=album.get("name") or "",
        spotify_id=track.get("id") or "",
        isrc=external_ids.get("isrc") or "",
    )


def get_track(
    url: str,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    sp: spotipy.Spotify | None = None,
) -> TrackInfo | None:
    """Return :class:`TrackInfo` for a Spotify track URL."""
    sp = sp or build_client(client_id, redirect_uri)
    data = sp.track(url)
    if data is not None:
        return _track_info(data)
    return None


def get_playlist(
    url: str,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    sp: spotipy.Spotify | None = None,
) -> list[TrackInfo]:
    """Return a list of :class:`TrackInfo` for every track in a Spotify playlist."""
    sp = sp or build_client(client_id, redirect_uri)
    tracks: list[TrackInfo] = []

    results = sp.playlist_items(url)
    while results:
        for item in results["items"]:
            # The API returns playlist items under "track"; older code in this
            # repo read "item", so accept either rather than silently returning
            # an empty playlist.
            track = item.get("track") or item.get("item")
            info = _track_info(track) if track else None
            if info is None:
                continue
            tracks.append(info)
        results = sp.next(results) if results.get("next") else None

    return tracks


def list_playlists(
    client_id: str | None = None,
    redirect_uri: str | None = None,
    sp: spotipy.Spotify | None = None,
) -> list[PlaylistInfo]:
    """Return every playlist belonging to the authenticated user."""
    sp = sp or build_client(client_id, redirect_uri)
    playlists: list[PlaylistInfo] = []

    results = sp.current_user_playlists()
    while results:
        for item in results["items"]:
            if not item:
                continue
            playlist_id = item.get("id")
            if not playlist_id:
                continue
            tracks = item.get("tracks") or {}
            playlists.append(
                PlaylistInfo(
                    id=str(playlist_id),
                    name=item.get("name") or "",
                    track_count=int(tracks.get("total") or 0),
                )
            )
        results = sp.next(results) if results.get("next") else None

    return playlists
