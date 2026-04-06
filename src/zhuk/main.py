"""CLI entry point for zhuk."""

from __future__ import annotations

import argparse
import sys

from zhuk.downloader import download_track, download_tracks
from zhuk.matcher import find_missing_tracks
from zhuk.spotify import get_playlist, get_track

TRACK_URL_HINT = "open.spotify.com/track/"
PLAYLIST_URL_HINT = "open.spotify.com/playlist/"


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
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync mode: only download tracks not already present locally",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Number of parallel download workers (default: 4)",
    )
    args = parser.parse_args(argv)

    url: str = args.url
    output_dir: str = args.output
    sync_mode: bool = args.sync
    max_workers: int = args.workers

    if PLAYLIST_URL_HINT in url:
        print(f"Fetching playlist from Spotify…")
        tracks = get_playlist(url)
        print(f"Found {len(tracks)} track(s) in playlist.")
        
        if sync_mode:
            print(f"Scanning {output_dir} for existing tracks…")
            missing_tracks, matched_tracks = find_missing_tracks(tracks, output_dir, threshold=90)
            
            print(f"  ✓ {len(matched_tracks)} track(s) already present")
            print(f"  → {len(missing_tracks)} track(s) to download")
            
            if missing_tracks:
                print(f"Starting download…")
                paths = download_tracks(missing_tracks, output_dir=output_dir, max_workers=max_workers)
                for path in paths:
                    print(f"  ✓ {path}")
            else:
                print("All tracks are already present. Nothing to download.")
        else:
            print(f"Starting download…")
            paths = download_tracks(tracks, output_dir=output_dir, max_workers=max_workers)
            for path in paths:
                print(f"  ✓ {path}")
    elif TRACK_URL_HINT in url:
        print(f"Fetching track from Spotify…")
        track = get_track(url)
        assert track is not None
        
        if sync_mode:
            print(f"Scanning {output_dir} for existing tracks…")
            missing_tracks, matched_tracks = find_missing_tracks([track], output_dir, threshold=90)
            
            if matched_tracks:
                print(f"  ✓ Track already present: {matched_tracks[0][1].filepath}")
                print("Nothing to download.")
            else:
                print(f"Downloading: {track.search_query()}")
                path = download_track(track, output_dir=output_dir)
                print(f"  ✓ {path}")
        else:
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
