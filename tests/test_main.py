"""Unit tests for zhuk.main (CLI)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from zhuk.main import main


class TestMainCLI:
    @patch("zhuk.main.get_track")
    @patch("zhuk.main.download_track")
    def test_track_url_downloads_single_track(self, mock_download, mock_get_track):
        from zhuk.spotify import TrackInfo

        mock_get_track.return_value = TrackInfo(title="Song", artist="Artist")
        mock_download.return_value = "/downloads/Song.mp3"

        main(["https://open.spotify.com/track/abc123"])

        mock_get_track.assert_called_once_with("https://open.spotify.com/track/abc123")
        mock_download.assert_called_once()

    @patch("zhuk.main.get_playlist")
    @patch("zhuk.main.download_tracks")
    def test_playlist_url_downloads_all_tracks(self, mock_download, mock_get_playlist):
        from zhuk.spotify import TrackInfo

        mock_get_playlist.return_value = [
            TrackInfo(title="Song A", artist="A"),
            TrackInfo(title="Song B", artist="B"),
        ]
        mock_download.return_value = ["/downloads/Song A.mp3", "/downloads/Song B.mp3"]

        main(["https://open.spotify.com/playlist/pl123"])

        mock_get_playlist.assert_called_once_with(
            "https://open.spotify.com/playlist/pl123"
        )
        mock_download.assert_called_once()

    def test_invalid_url_exits_with_error(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["https://example.com/not-spotify"])
        assert exc_info.value.code == 1

    @patch("zhuk.main.get_track")
    @patch("zhuk.main.download_track")
    def test_custom_output_dir_passed_through(self, mock_download, mock_get_track):
        from zhuk.spotify import TrackInfo

        mock_get_track.return_value = TrackInfo(title="Song", artist="Artist")
        mock_download.return_value = "/my_dir/Song.mp3"

        main(
            [
                "https://open.spotify.com/track/abc",
                "--output",
                "/my_dir",
            ]
        )

        _, kwargs = mock_download.call_args
        assert kwargs.get("output_dir") == "/my_dir"
