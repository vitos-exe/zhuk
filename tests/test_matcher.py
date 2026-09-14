"""Unit tests for zhuk.matcher."""

import os
from pathlib import Path
from unittest.mock import patch

import mutagen.id3

from zhuk.matcher import (
    LocalTrack,
    find_missing_tracks,
    match_track,
    read_id3_tags,
    scan_mp3_files,
)
from zhuk.spotify import TrackInfo


class TestScanMp3Files:
    def test_returns_empty_list_for_nonexistent_dir(self, tmp_path):
        assert scan_mp3_files(tmp_path / "nonexistent") == []

    def test_returns_only_mp3_files(self, tmp_path):
        (tmp_path / "song1.mp3").touch()
        (tmp_path / "song2.MP3").touch()
        (tmp_path / "readme.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "song3.mp3").touch()

        files = scan_mp3_files(tmp_path)
        assert len(files) == 2
        # Use basename for comparison since absolute paths might differ slightly
        basenames = [os.path.basename(f) for f in files]
        assert "song1.mp3" in basenames
        assert "song2.MP3" in basenames


class TestReadId3Tags:
    def test_reads_tags_successfully(self, tmp_path):
        mp3_path = tmp_path / "song.mp3"
        tags = mutagen.id3.ID3()
        tags["TIT2"] = mutagen.id3.TIT2(encoding=3, text="Title")
        tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text="Artist")
        tags.save(mp3_path)

        local_track = read_id3_tags(mp3_path)
        assert local_track is not None
        assert local_track.title == "Title"
        assert local_track.artist == "Artist"
        assert local_track.filepath == str(mp3_path)

    def test_returns_none_if_tags_missing(self, tmp_path):
        mp3_path = tmp_path / "song.mp3"
        with open(mp3_path, "wb") as f:
            f.write(b"not an mp3")

        assert read_id3_tags(mp3_path) is None


class TestMatchTrack:
    def test_exact_match(self):
        spotify_track = TrackInfo(title="Song", artist="Artist")
        local_tracks = [LocalTrack(filepath="path", title="Song", artist="Artist")]

        match = match_track(spotify_track, local_tracks)
        assert match == local_tracks[0]

    def test_fuzzy_match(self):
        spotify_track = TrackInfo(title="Song!", artist="Artist")
        local_tracks = [LocalTrack(filepath="path", title="Song", artist="Artist")]

        match = match_track(spotify_track, local_tracks)
        assert match == local_tracks[0]

    def test_no_match(self):
        spotify_track = TrackInfo(title="Other", artist="Artist")
        local_tracks = [LocalTrack(filepath="path", title="Song", artist="Artist")]

        match = match_track(spotify_track, local_tracks)
        assert match is None

    def test_empty_local_tracks(self):
        spotify_track = TrackInfo(title="Song", artist="Artist")
        assert match_track(spotify_track, []) is None


class TestFindMissingTracks:
    @patch("zhuk.matcher.scan_mp3_files")
    @patch("zhuk.matcher.read_id3_tags")
    def test_finds_missing_and_matched(self, mock_read_id3, mock_scan):
        mock_scan.return_value = ["song1.mp3", "song2.mp3"]
        mock_read_id3.side_effect = [
            LocalTrack(filepath="song1.mp3", title="Matched", artist="Artist"),
            LocalTrack(filepath="song2.mp3", title="Other", artist="Artist"),
        ]

        spotify_tracks = [
            TrackInfo(title="Matched", artist="Artist"),
            TrackInfo(title="Missing", artist="Artist"),
        ]

        missing, matched = find_missing_tracks(spotify_tracks, Path("dir"))

        assert len(missing) == 1
        assert missing[0].title == "Missing"
        assert len(matched) == 1
        assert matched[0][0].title == "Matched"
        assert matched[0][1].filepath == "song1.mp3"


class TestIsProtected:
    def test_dotfiles_and_playlists_are_protected(self, tmp_path):
        from zhuk.matcher import is_protected

        assert is_protected(tmp_path / ".DS_Store")
        assert is_protected(tmp_path / ".zhuk.json")
        assert is_protected(tmp_path / "Set.m3u8")
        assert is_protected(tmp_path / "Set.M3U8")
        assert not is_protected(tmp_path / "song.mp3")


class TestScanSyncFiles:
    def test_excludes_protected_and_directories(self, tmp_path):
        from zhuk.matcher import scan_sync_files

        (tmp_path / "song.mp3").touch()
        (tmp_path / "notes.txt").touch()
        (tmp_path / "Set.m3u8").touch()
        (tmp_path / ".DS_Store").touch()
        (tmp_path / "subdir").mkdir()

        names = sorted(p.name for p in scan_sync_files(tmp_path))
        # Mirror sync deletes unknown files, so non-MP3s are candidates too,
        # but directories and protected files never are.
        assert names == ["notes.txt", "song.mp3"]

    def test_missing_directory(self, tmp_path):
        from zhuk.matcher import scan_sync_files

        assert scan_sync_files(tmp_path / "nope") == []


class TestReadSpotifyId:
    def test_reads_embedded_id(self, tmp_path, make_mp3):
        from zhuk.matcher import read_spotify_id

        path = make_mp3(tmp_path / "a.mp3", spotify_id="abc123")
        assert read_spotify_id(path) == "abc123"

    def test_returns_none_without_id(self, tmp_path, make_mp3):
        from zhuk.matcher import read_spotify_id

        path = make_mp3(tmp_path / "a.mp3", spotify_id=None)
        assert read_spotify_id(path) is None

    def test_returns_none_for_unreadable_file(self, tmp_path):
        from zhuk.matcher import read_spotify_id

        path = tmp_path / "broken.mp3"
        path.write_text("not an mp3")
        assert read_spotify_id(path) is None


class TestIndexBySpotifyId:
    def test_splits_identified_and_unidentified(self, tmp_path, make_mp3):
        from zhuk.matcher import index_by_spotify_id

        make_mp3(tmp_path / "a.mp3", spotify_id="id1")
        make_mp3(tmp_path / "b.mp3", spotify_id=None)

        index, unidentified = index_by_spotify_id(tmp_path)

        assert set(index) == {"id1"}
        assert [p.name for p in unidentified] == ["b.mp3"]


class TestDiffPlaylist:
    def test_returns_missing_present_and_orphans(self, tmp_path, make_mp3):
        from zhuk.matcher import diff_playlist

        make_mp3(tmp_path / "a.mp3", spotify_id="id1")
        make_mp3(tmp_path / "stale.mp3", spotify_id="old")

        tracks = [TrackInfo("A", "X", spotify_id="id1"), TrackInfo("B", "Y", spotify_id="id2")]
        missing, present, orphans = diff_playlist(tracks, tmp_path)

        assert [t.spotify_id for t in missing] == ["id2"]
        assert set(present) == {"id1"}
        assert [p.name for p in orphans] == ["stale.mp3"]

    def test_track_without_id_is_always_missing(self, tmp_path):
        from zhuk.matcher import diff_playlist

        missing, present, orphans = diff_playlist([TrackInfo("A", "X")], tmp_path)

        assert len(missing) == 1
        assert present == {}
        assert orphans == []
