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
        mock_download.assert_called_once_with(
            missing, output_dir=Path("downloads").resolve(), max_workers=4
        )

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


class TestSyncCLI:
    """The sync command's job is selection resolution; syncing itself is tested
    in test_sync.py."""

    @staticmethod
    def _playlists():
        from zhuk.spotify import PlaylistInfo

        return [
            PlaylistInfo(id="a", name="House", track_count=2),
            PlaylistInfo(id="b", name="Techno", track_count=3),
        ]

    def _invoke(self, args, playlists=None, **patches):
        from zhuk.state import SyncState

        runner = CliRunner()
        with runner.isolated_filesystem():
            os.mkdir("music")
            with patch("zhuk.main.build_client"), patch(
                "zhuk.main.list_playlists",
                return_value=self._playlists() if playlists is None else playlists,
            ), patch("zhuk.main.sync_playlists", return_value=0) as mock_sync, patch(
                "zhuk.main.save_state"
            ), patch(
                "zhuk.main.load_state", return_value=patches.get("state", SyncState())
            ), patch(
                "zhuk.main.select_playlists",
                return_value=patches.get("picked", []),
            ) as mock_picker:
                result = runner.invoke(cli, ["sync", "-o", "music", *args])
        return result, mock_sync, mock_picker

    def test_playlist_option_selects_by_name(self):
        result, mock_sync, mock_picker = self._invoke(["--playlist", "Techno"])

        assert result.exit_code == 0
        assert [p.id for p in mock_sync.call_args[0][1]] == ["b"]
        mock_picker.assert_not_called()

    def test_playlist_option_warns_on_unknown(self):
        result, mock_sync, _ = self._invoke(["--playlist", "Nope"])

        assert "no playlist matched 'Nope'" in result.output
        assert mock_sync.call_args[0][1] == []

    def test_all_flag_selects_everything(self):
        _, mock_sync, mock_picker = self._invoke(["--all"])

        assert [p.id for p in mock_sync.call_args[0][1]] == ["a", "b"]
        mock_picker.assert_not_called()

    def test_opens_picker_when_no_stored_selection(self):
        _, _, mock_picker = self._invoke([], picked=[self._playlists()[0]])
        mock_picker.assert_called_once()

    def test_reuses_stored_selection_without_prompting(self):
        from zhuk.state import PlaylistRecord, SyncState

        state = SyncState([PlaylistRecord(id="b", name="Techno", folder="Techno")])
        _, mock_sync, mock_picker = self._invoke([], state=state)

        mock_picker.assert_not_called()
        assert [p.id for p in mock_sync.call_args[0][1]] == ["b"]

    def test_select_flag_reopens_picker(self):
        from zhuk.state import PlaylistRecord, SyncState

        state = SyncState([PlaylistRecord(id="b", name="Techno", folder="Techno")])
        _, _, mock_picker = self._invoke(
            ["--select"], state=state, picked=[self._playlists()[0]]
        )

        mock_picker.assert_called_once()
        assert mock_picker.call_args.kwargs["preselected"] == {"b"}

    def test_warns_about_vanished_stored_playlist(self):
        from zhuk.state import PlaylistRecord, SyncState

        state = SyncState([PlaylistRecord(id="gone", name="Old", folder="Old")])
        result, _, _ = self._invoke([], state=state)

        assert "no longer available" in result.output

    def test_aborts_when_picker_returns_nothing(self):
        result, mock_sync, _ = self._invoke([], picked=[])

        assert result.exit_code == 0
        assert "No playlists selected." in result.output
        mock_sync.assert_not_called()

    def test_errors_when_account_has_no_playlists(self):
        result, mock_sync, _ = self._invoke([], playlists=[])

        assert result.exit_code == 1
        mock_sync.assert_not_called()

    def test_dry_run_does_not_save_state(self):
        runner = CliRunner()
        from zhuk.state import SyncState

        with runner.isolated_filesystem():
            os.mkdir("music")
            with patch("zhuk.main.build_client"), patch(
                "zhuk.main.list_playlists", return_value=self._playlists()
            ), patch("zhuk.main.sync_playlists", return_value=0), patch(
                "zhuk.main.load_state", return_value=SyncState()
            ), patch("zhuk.main.save_state") as mock_save:
                runner.invoke(cli, ["sync", "-o", "music", "--all", "--dry-run"])

        mock_save.assert_not_called()

    def test_creates_output_directory(self):
        runner = CliRunner()
        from zhuk.state import SyncState

        with runner.isolated_filesystem():
            with patch("zhuk.main.build_client"), patch(
                "zhuk.main.list_playlists", return_value=self._playlists()
            ), patch("zhuk.main.sync_playlists", return_value=0), patch(
                "zhuk.main.load_state", return_value=SyncState()
            ), patch("zhuk.main.save_state"):
                runner.invoke(cli, ["sync", "-o", "new_dir", "--all"])
                assert Path("new_dir").is_dir()

    def test_forwards_flags(self):
        _, mock_sync, _ = self._invoke(
            ["--all", "-j", "8", "--no-playlist-file", "--yes", "--force"]
        )

        kwargs = mock_sync.call_args.kwargs
        assert kwargs["jobs"] == 8
        assert kwargs["write_playlist_file"] is False
        assert kwargs["assume_yes"] is True
        assert kwargs["force"] is True
