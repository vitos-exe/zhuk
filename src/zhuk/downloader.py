"""YouTube search and MP3 download via yt-dlp."""

from __future__ import annotations

import os

import mutagen.id3
import yt_dlp

from zhuk.spotify import TrackInfo

_DEFAULT_OUTPUT_DIR = "downloads"


def _write_id3_tags(mp3_path: str, track: TrackInfo) -> None:
    """Embed ID3 title, artist and album tags into an MP3 file."""
    try:
        tags = mutagen.id3.ID3(mp3_path)
    except mutagen.id3.ID3NoHeaderError:
        tags = mutagen.id3.ID3()

    tags["TIT2"] = mutagen.id3.TIT2(encoding=3, text=track.title)
    tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text=track.artist)
    if track.album:
        tags["TALB"] = mutagen.id3.TALB(encoding=3, text=track.album)

    tags.save(mp3_path)


def download_track(track: TrackInfo, output_dir: str = _DEFAULT_OUTPUT_DIR) -> str:
    """Search YouTube for *track* and download the best match as an MP3.

    Parameters
    ----------
    track:
        Metadata for the song to download.
    output_dir:
        Directory where the MP3 file will be saved.  Created automatically
        if it does not already exist.

    Returns
    -------
    str
        Absolute path to the downloaded MP3 file.
    """
    os.makedirs(output_dir, exist_ok=True)

    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "default_search": "ytsearch1",
        "noplaylist": True,
    }

    query = track.search_query()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        # yt-dlp replaces the extension after post-processing
        base, _ = os.path.splitext(filename)
        mp3_path = base + ".mp3"

    mp3_path = os.path.abspath(mp3_path)
    _write_id3_tags(mp3_path, track)
    return mp3_path


def download_tracks(
    tracks: list[TrackInfo], output_dir: str = _DEFAULT_OUTPUT_DIR
) -> list[str]:
    """Download each track in *tracks* and return their MP3 paths."""
    paths: list[str] = []
    for track in tracks:
        path = download_track(track, output_dir=output_dir)
        paths.append(path)
    return paths
