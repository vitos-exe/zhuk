"""Unit tests for zhuk.main (CLI)."""

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from zhuk.main import cli
from zhuk.spotify import TrackInfo


class TestMainCLI:
    @patch("zhuk.main.get_track")
    @patch("zhuk.main.download_track")
    def test_track_url_downloads_single_track(self, mock_download, mock_get_track):
        mock_get_track.return_value = TrackInfo(title="Song", artist="Artist")
        mock_download.return_value = "/downloads/Song.mp3"
        
        runner = CliRunner()
        runner.invoke(cli, ['download', 'https://open.spotify.com/track/abc123'])

        mock_get_track.assert_called_once_with("https://open.spotify.com/track/abc123", client_id=None, redirect_uri=None)
        mock_download.assert_called_once()

    @patch("zhuk.main.get_playlist")
    @patch("zhuk.main.download_tracks")
    def test_playlist_url_downloads_all_tracks(self, mock_download, mock_get_playlist):
        mock_get_playlist.return_value = [
            TrackInfo(title="Song A", artist="A"),
            TrackInfo(title="Song B", artist="B"),
        ]
        mock_download.return_value = ["/downloads/Song A.mp3", "/downloads/Song B.mp3"]

        runner = CliRunner()
        runner.invoke(cli, ['download', 'https://open.spotify.com/playlist/pl123'])

        mock_get_playlist.assert_called_once_with(
            "https://open.spotify.com/playlist/pl123", client_id=None, redirect_uri=None
        )
        mock_download.assert_called_once()

    def test_invalid_url_exits_with_error(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['download', "https://example.com/not-spotify"])
        assert result.exit_code == 1

    @patch("zhuk.main.get_track")
    @patch("zhuk.main.download_track")
    def test_custom_output_dir_passed_through(self, mock_download, mock_get_track):
        mock_get_track.return_value = TrackInfo(title="Song", artist="Artist")
        mock_download.return_value = "/my_dir/Song.mp3"

        runner = CliRunner()
        with runner.isolated_filesystem():
            os.mkdir("my_dir")
            result = runner.invoke(cli, [
                    'download',
                    "https://open.spotify.com/track/abc",
                    "--output",
                    "my_dir",
                ])

        _, kwargs = mock_download.call_args
        assert kwargs.get("output_dir").name == "my_dir"

    @patch("zhuk.main.get_track")
    @patch("zhuk.main.download_track")
    def test_track_download_error_is_skipped(self, mock_download, mock_get_track):
        mock_get_track.return_value = TrackInfo(title="Song", artist="Artist")
        mock_download.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ['download', 'https://open.spotify.com/track/abc123'])

        assert result.exit_code == 0
        assert "✓" not in result.output

    @patch("zhuk.main.get_track")
    @patch("zhuk.main.find_missing_tracks")
    @patch("zhuk.main.download_track")
    def test_track_already_exists_skips_download(self, mock_download, mock_find_missing, mock_get_track):
        track = TrackInfo(title="Song", artist="Artist")
        mock_get_track.return_value = track
        from zhuk.matcher import LocalTrack
        mock_find_missing.return_value = ([], [(track, LocalTrack(filepath="downloads/Song.mp3", title="Song", artist="Artist"))])

        runner = CliRunner()
        result = runner.invoke(cli, ['download', 'https://open.spotify.com/track/abc123'])

        assert "Skipping (already exists)" in result.output
        mock_download.assert_not_called()

    @patch("zhuk.main.get_playlist")
    @patch("zhuk.main.find_missing_tracks")
    @patch("zhuk.main.download_tracks")
    def test_playlist_partially_exists_skips_some(self, mock_download, mock_find_missing, mock_get_playlist):
        tracks = [
            TrackInfo(title="Song A", artist="A"),
            TrackInfo(title="Song B", artist="B"),
        ]
        mock_get_playlist.return_value = tracks
        from zhuk.matcher import LocalTrack
        matched = [(tracks[0], LocalTrack(filepath="downloads/A.mp3", title="Song A", artist="A"))]
        missing = [tracks[1]]
        mock_find_missing.return_value = (missing, matched)
        mock_download.return_value = ["/downloads/B.mp3"]

        runner = CliRunner()
        result = runner.invoke(cli, ['download', 'https://open.spotify.com/playlist/pl123'])

        assert "Skipping 1 track(s) already in" in result.output
        assert "Starting download of 1 missing track(s)" in result.output
        mock_download.assert_called_once_with(missing, output_dir=Path("downloads").resolve())

    @patch("zhuk.main.get_playlist")
    @patch("zhuk.main.find_missing_tracks")
    @patch("zhuk.main.download_tracks")
    def test_playlist_all_exist_skips_all(self, mock_download, mock_find_missing, mock_get_playlist):
        tracks = [TrackInfo(title="Song A", artist="A")]
        mock_get_playlist.return_value = tracks
        from zhuk.matcher import LocalTrack
        mock_find_missing.return_value = ([], [(tracks[0], LocalTrack(filepath="downloads/A.mp3", title="Song A", artist="A"))])

        runner = CliRunner()
        result = runner.invoke(cli, ['download', 'https://open.spotify.com/playlist/pl123'])

        assert "All tracks already downloaded" in result.output
        mock_download.assert_not_called()

    @patch("zhuk.main.get_playlist")
    @patch("zhuk.main.download_tracks")
    def test_playlist_download_error_is_skipped(self, mock_download, mock_get_playlist):
        mock_get_playlist.return_value = [TrackInfo(title="Song A", artist="A")]
        mock_download.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ['download', 'https://open.spotify.com/playlist/pl123'])

        assert result.exit_code == 0
        assert "✓" not in result.output
