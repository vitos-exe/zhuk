"""Unit tests for zhuk.downloader."""

import os
from unittest.mock import MagicMock, call, patch

import mutagen.id3

from zhuk.downloader import download_track, download_tracks, write_id3_tags
from zhuk.spotify import TrackInfo


class TestWriteId3Tags:
    def test_writes_title_artist_album(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        # Create a minimal valid MP3 file with an ID3 header
        tags = mutagen.id3.ID3()
        tags.save(mp3_path)

        track = TrackInfo(title="Bohemian Rhapsody", artist="Queen", album="A Night at the Opera")
        write_id3_tags(mp3_path, track)

        saved = mutagen.id3.ID3(mp3_path)
        assert str(saved["TIT2"]) == "Bohemian Rhapsody"
        assert str(saved["TPE1"]) == "Queen"
        assert str(saved["TALB"]) == "A Night at the Opera"

    def test_writes_title_and_artist_without_album(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        tags = mutagen.id3.ID3()
        tags.save(mp3_path)

        track = TrackInfo(title="Song", artist="Artist")
        write_id3_tags(mp3_path, track)

        saved = mutagen.id3.ID3(mp3_path)
        assert str(saved["TIT2"]) == "Song"
        assert str(saved["TPE1"]) == "Artist"
        assert "TALB" not in saved

    def test_creates_id3_header_if_missing(self, tmp_path):
        mp3_path = str(tmp_path / "song.mp3")
        # Write a file with no ID3 header at all
        mp3_path_obj = tmp_path / "song.mp3"
        mp3_path_obj.write_bytes(b"\xff\xfb\x90\x00" * 10)

        track = TrackInfo(title="Song", artist="Artist", album="Album")
        write_id3_tags(str(mp3_path_obj), track)

        saved = mutagen.id3.ID3(str(mp3_path_obj))
        assert str(saved["TIT2"]) == "Song"
        assert str(saved["TPE1"]) == "Artist"
        assert str(saved["TALB"]) == "Album"



class TestDownloadTrack:
    def _make_info(self, title="Bohemian Rhapsody"):
        return {
            "title": title,
            "ext": "webm",
            "id": "abc123",
        }

    @patch("zhuk.downloader._write_id3_tags")
    @patch("zhuk.downloader.yt_dlp.YoutubeDL")
    def test_calls_ydl_with_search_query(self, mock_ydl_cls, mock_write_tags, tmp_path):
        track = TrackInfo(title="Bohemian Rhapsody", artist="Queen")
        info = self._make_info()

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = info
        mock_ydl.prepare_filename.return_value = str(tmp_path / "Bohemian Rhapsody.webm")
        mock_ydl_cls.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = download_track(track, output_dir=str(tmp_path))

        mock_ydl.extract_info.assert_called_once_with(
            "Queen - Bohemian Rhapsody", download=True
        )
        assert result.endswith(".mp3")

    @patch("zhuk.downloader._write_id3_tags")
    @patch("zhuk.downloader.yt_dlp.YoutubeDL")
    def test_unwraps_entries(self, mock_ydl_cls, mock_write_tags, tmp_path):
        track = TrackInfo(title="Song", artist="Artist")
        entry_info = self._make_info("Song")
        result_info = {"entries": [entry_info]}

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = result_info
        mock_ydl.prepare_filename.return_value = str(tmp_path / "Song.webm")
        mock_ydl_cls.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = download_track(track, output_dir=str(tmp_path))

        mock_ydl.prepare_filename.assert_called_once_with(entry_info)
        assert result.endswith(".mp3")

    @patch("zhuk.downloader._write_id3_tags")
    @patch("zhuk.downloader.yt_dlp.YoutubeDL")
    def test_creates_output_dir(self, mock_ydl_cls, mock_write_tags, tmp_path):
        track = TrackInfo(title="Song", artist="Artist")
        output_dir = str(tmp_path / "new_dir")

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = self._make_info()
        mock_ydl.prepare_filename.return_value = os.path.join(output_dir, "Song.webm")
        mock_ydl_cls.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        download_track(track, output_dir=output_dir)

        assert os.path.isdir(output_dir)

    @patch("zhuk.downloader._write_id3_tags")
    @patch("zhuk.downloader.yt_dlp.YoutubeDL")
    def test_ydl_opts_include_mp3_postprocessor(self, mock_ydl_cls, mock_write_tags, tmp_path):
        track = TrackInfo(title="Song", artist="Artist")

        captured_opts: dict = {}

        def capture_opts(opts):
            captured_opts.update(opts)
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = self._make_info()
            mock_ydl.prepare_filename.return_value = str(tmp_path / "Song.webm")
            mock_ydl_cls.return_value.__enter__ = lambda s: mock_ydl
            mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)
            return mock_ydl_cls.return_value

        mock_ydl_cls.side_effect = capture_opts

        download_track(track, output_dir=str(tmp_path))

        postprocessors = captured_opts.get("postprocessors", [])
        codecs = [pp.get("preferredcodec") for pp in postprocessors]
        assert "mp3" in codecs

    @patch("zhuk.downloader._write_id3_tags")
    @patch("zhuk.downloader.yt_dlp.YoutubeDL")
    def test_writes_id3_tags_after_download(self, mock_ydl_cls, mock_write_tags, tmp_path):
        track = TrackInfo(title="Song", artist="Artist", album="Album")
        mp3_filename = str(tmp_path / "Song.mp3")

        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = self._make_info("Song")
        mock_ydl.prepare_filename.return_value = str(tmp_path / "Song.webm")
        mock_ydl_cls.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = download_track(track, output_dir=str(tmp_path))

        mock_write_tags.assert_called_once_with(result, track)


class TestDownloadTracks:
    @patch("zhuk.downloader.download_track")
    def test_downloads_all_tracks(self, mock_download_track, tmp_path):
        tracks = [
            TrackInfo(title="Song A", artist="Artist A"),
            TrackInfo(title="Song B", artist="Artist B"),
        ]
        mock_download_track.side_effect = ["/out/Song A.mp3", "/out/Song B.mp3"]

        paths = download_tracks(tracks, output_dir=str(tmp_path))

        assert set(paths) == {"/out/Song A.mp3", "/out/Song B.mp3"}
        assert mock_download_track.call_count == 2
        mock_download_track.assert_any_call(tracks[0], output_dir=str(tmp_path))
        mock_download_track.assert_any_call(tracks[1], output_dir=str(tmp_path))

    @patch("zhuk.downloader.download_track")
    def test_preserves_order(self, mock_download_track, tmp_path):
        tracks = [
            TrackInfo(title=f"Song {i}", artist="Artist")
            for i in range(6)
        ]
        expected = [f"/out/Song {i}.mp3" for i in range(6)]
        mock_download_track.side_effect = expected[:]

        paths = download_tracks(tracks, output_dir=str(tmp_path), max_workers=3)

        assert paths == expected

    @patch("zhuk.downloader.download_track")
    def test_empty_list(self, mock_download_track, tmp_path):
        paths = download_tracks([], output_dir=str(tmp_path))
        assert paths == []
        mock_download_track.assert_not_called()

    @patch("zhuk.downloader.download_track")
    def test_respects_max_workers(self, mock_download_track, tmp_path):
        tracks = [TrackInfo(title=f"Song {i}", artist="Artist") for i in range(4)]
        mock_download_track.side_effect = [f"/out/Song {i}.mp3" for i in range(4)]

        paths = download_tracks(tracks, output_dir=str(tmp_path), max_workers=2)

        assert mock_download_track.call_count == 4
        assert len(paths) == 4
