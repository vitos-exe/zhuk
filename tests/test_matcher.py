"""Unit tests for zhuk.matcher."""

import os
from unittest.mock import MagicMock, patch

import mutagen.id3
import pytest

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
        assert scan_mp3_files(str(tmp_path / "nonexistent")) == []

    def test_returns_only_mp3_files(self, tmp_path):
        (tmp_path / "song1.mp3").touch()
        (tmp_path / "song2.MP3").touch()
        (tmp_path / "readme.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "song3.mp3").touch()

        files = scan_mp3_files(str(tmp_path))
        assert len(files) == 2
        # Use basename for comparison since absolute paths might differ slightly
        basenames = [os.path.basename(f) for f in files]
        assert "song1.mp3" in basenames
        assert "song2.MP3" in basenames


class TestReadId3Tags:
    def test_reads_tags_successfully(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        tags = mutagen.id3.ID3()
        tags["TIT2"] = mutagen.id3.TIT2(encoding=3, text="Title")
        tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text="Artist")
        tags.save(mp3_path)

        local_track = read_id3_tags(mp3_path)
        assert local_track is not None
        assert local_track.title == "Title"
        assert local_track.artist == "Artist"
        assert local_track.filepath == mp3_path

    def test_returns_none_if_tags_missing(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
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

        missing, matched = find_missing_tracks(spotify_tracks, "dir")

        assert len(missing) == 1
        assert missing[0].title == "Missing"
        assert len(matched) == 1
        assert matched[0][0].title == "Matched"
        assert matched[0][1].filepath == "song1.mp3"
