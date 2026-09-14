"""Unit tests for zhuk.playlist_file."""

from zhuk.playlist_file import playlist_file_path, write_m3u8
from zhuk.spotify import TrackInfo


def _track(spotify_id, title="Song", artist="Artist"):
    return TrackInfo(title=title, artist=artist, spotify_id=spotify_id)


class TestPlaylistFilePath:
    def test_sanitizes_playlist_name(self, tmp_path):
        path = playlist_file_path(tmp_path, "House/Techno")
        assert path.name == "House-Techno.m3u8"


class TestWriteM3u8:
    def test_writes_relative_paths(self, tmp_path):
        local = tmp_path / "a.mp3"
        local.touch()

        path = write_m3u8(tmp_path, "Set", [_track("id1")], {"id1": local})
        content = path.read_text()

        assert content.startswith("#EXTM3U\n")
        assert "a.mp3" in content
        # Relative so the folder survives being copied to a USB stick.
        assert str(tmp_path) not in content

    def test_preserves_playlist_order(self, tmp_path):
        first = tmp_path / "first.mp3"
        second = tmp_path / "second.mp3"
        first.touch()
        second.touch()

        tracks = [_track("id2", title="Second"), _track("id1", title="First")]
        path = write_m3u8(tmp_path, "Set", tracks, {"id1": first, "id2": second})

        lines = [ln for ln in path.read_text().splitlines() if ln.endswith(".mp3")]
        assert lines == ["second.mp3", "first.mp3"]

    def test_omits_tracks_without_local_file(self, tmp_path):
        local = tmp_path / "a.mp3"
        local.touch()

        tracks = [_track("id1"), _track("missing", title="Not Downloaded")]
        path = write_m3u8(tmp_path, "Set", tracks, {"id1": local})

        assert "Not Downloaded" not in path.read_text()

    def test_writes_extinf_per_entry(self, tmp_path):
        local = tmp_path / "a.mp3"
        local.touch()

        path = write_m3u8(
            tmp_path, "Set", [_track("id1", title="T", artist="A")], {"id1": local}
        )
        assert "#EXTINF:-1,A - T" in path.read_text()

    def test_creates_folder_if_absent(self, tmp_path):
        folder = tmp_path / "new"
        path = write_m3u8(folder, "Set", [], {})
        assert path.exists()
