"""Unit tests for zhuk.spotify."""

from unittest.mock import MagicMock, patch

import pytest

from zhuk.spotify import TrackInfo, get_playlist, get_track


class TestTrackInfo:
    def test_search_query(self):
        track = TrackInfo(title="Bohemian Rhapsody", artist="Queen")
        assert track.search_query() == "Queen - Bohemian Rhapsody"

    def test_dataclass_fields(self):
        track = TrackInfo(title="Song", artist="Artist", album="Album")
        assert track.title == "Song"
        assert track.artist == "Artist"
        assert track.album == "Album"

    def test_album_defaults_to_empty_string(self):
        track = TrackInfo(title="Song", artist="Artist")
        assert track.album == ""


class TestGetTrack:
    def _make_spotify_track_response(self):
        return {
            "name": "Bohemian Rhapsody",
            "artists": [{"name": "Queen"}],
            "album": {"name": "A Night at the Opera"},
        }

    @patch("zhuk.spotify._build_client")
    def test_returns_track_info(self, mock_build):
        mock_sp = MagicMock()
        mock_sp.track.return_value = self._make_spotify_track_response()
        mock_build.return_value = mock_sp

        track = get_track("https://open.spotify.com/track/abc123")

        assert track.title == "Bohemian Rhapsody"
        assert track.artist == "Queen"
        assert track.album == "A Night at the Opera"
        mock_sp.track.assert_called_once_with("https://open.spotify.com/track/abc123")

    @patch("zhuk.spotify._build_client")
    def test_uses_first_artist(self, mock_build):
        mock_sp = MagicMock()
        mock_sp.track.return_value = {
            "name": "Track",
            "artists": [{"name": "FirstArtist"}, {"name": "SecondArtist"}],
            "album": {"name": "Some Album"},
        }
        mock_build.return_value = mock_sp

        track = get_track("https://open.spotify.com/track/xyz")

        assert track.artist == "FirstArtist"


class TestGetPlaylist:
    def _make_page(self, track_names, next_url=None):
        items = [
            {
                "track": {
                    "name": name,
                    "artists": [{"name": f"Artist{i}"}],
                    "album": {"name": f"Album{i}"},
                }
            }
            for i, name in enumerate(track_names)
        ]
        return {"items": items, "next": next_url}

    @patch("zhuk.spotify._build_client")
    def test_single_page(self, mock_build):
        mock_sp = MagicMock()
        mock_sp.playlist_tracks.return_value = self._make_page(["Song A", "Song B"])
        mock_sp.next.return_value = None
        mock_build.return_value = mock_sp

        tracks = get_playlist("https://open.spotify.com/playlist/pl123")

        assert len(tracks) == 2
        assert tracks[0].title == "Song A"
        assert tracks[1].title == "Song B"
        assert tracks[0].album == "Album0"
        assert tracks[1].album == "Album1"

    @patch("zhuk.spotify._build_client")
    def test_skips_null_tracks(self, mock_build):
        mock_sp = MagicMock()
        mock_sp.playlist_tracks.return_value = {
            "items": [
                {"track": None},
                {
                    "track": {
                        "name": "Real Song",
                        "artists": [{"name": "Artist"}],
                        "album": {"name": "Real Album"},
                    }
                },
            ],
            "next": None,
        }
        mock_sp.next.return_value = None
        mock_build.return_value = mock_sp

        tracks = get_playlist("https://open.spotify.com/playlist/pl456")

        assert len(tracks) == 1
        assert tracks[0].title == "Real Song"
        assert tracks[0].album == "Real Album"

    @patch("zhuk.spotify._build_client")
    def test_multiple_pages(self, mock_build):
        page1 = self._make_page(["Song 1", "Song 2"], next_url="next_url")
        page2 = self._make_page(["Song 3"])
        mock_sp = MagicMock()
        mock_sp.playlist_tracks.return_value = page1
        mock_sp.next.return_value = page2
        mock_build.return_value = mock_sp

        tracks = get_playlist("https://open.spotify.com/playlist/pl789")

        assert len(tracks) == 3
        assert [t.title for t in tracks] == ["Song 1", "Song 2", "Song 3"]


class TestBuildClient:
    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SPOTIPY_CLIENT_ID", raising=False)
        monkeypatch.delenv("SPOTIPY_CLIENT_SECRET", raising=False)

        from zhuk.spotify import build_client

        with pytest.raises(EnvironmentError, match="SPOTIPY_CLIENT_ID"):
            build_client()
