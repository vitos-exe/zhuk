"""CLI entry point for zhuk."""

from __future__ import annotations

import argparse
import sys

from zhuk.downloader import download_track, download_tracks
from zhuk.spotify import get_playlist, get_track

_TRACK_URL_HINT = "open.spotify.com/track/"
_PLAYLIST_URL_HINT = "open.spotify.com/playlist/"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="zhuk",
        description="Download a Spotify track or playlist as MP3 from YouTube.",
    )
    parser.add_argument(
        "url",
        help="Spotify track or playlist URL",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        metavar="DIR",
        help="Directory to save MP3 files (default: downloads)",
    )
    args = parser.parse_args(argv)

    url: str = args.url
    output_dir: str = args.output

    if _PLAYLIST_URL_HINT in url:
        print(f"Fetching playlist from Spotify…")
        tracks = get_playlist(url)
        print(f"Found {len(tracks)} track(s). Starting download…")
        paths = download_tracks(tracks, output_dir=output_dir)
        for path in paths:
            print(f"  ✓ {path}")
    elif _TRACK_URL_HINT in url:
        print(f"Fetching track from Spotify…")
        track = get_track(url)
        print(f"Downloading: {track.search_query()}")
        path = download_track(track, output_dir=output_dir)
        print(f"  ✓ {path}")
    else:
        print(
            "Error: URL must be a Spotify track or playlist URL.\n"
            "  Track:    https://open.spotify.com/track/<id>\n"
            "  Playlist: https://open.spotify.com/playlist/<id>",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
