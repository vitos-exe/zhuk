import sys
from pathlib import Path

import click

from zhuk.downloader import DEFAULT_MAX_WORKERS, download_track, download_tracks
from zhuk.matcher import find_missing_tracks
from zhuk.spotify import get_playlist, get_track

TRACK_URL_HINT = "open.spotify.com/track/"
PLAYLIST_URL_HINT = "open.spotify.com/playlist/"


@click.group()
@click.option('--client-id', envvar='SPOTIPY_CLIENT_ID', help='Spotify client ID')
@click.option('--redirect-uri', envvar='SPOTIPY_REDIRECT_URI', help='Spotify redirect URI')
@click.pass_context
def cli(ctx, client_id, redirect_uri):
    ctx.ensure_object(dict)
    ctx.obj['client_id'] = client_id
    ctx.obj['redirect_uri'] = redirect_uri


@click.command()
@click.argument('url')
@click.option(
        '-o',
        '--output',
        help="Directory to save MP3 files (default: downloads)",
        type=click.Path(file_okay=False, resolve_path=True, writable=True, path_type=Path),
        default=Path("downloads")
        )
@click.option(
        '-j',
        '--jobs',
        help="Number of tracks to download in parallel (default: 4)",
        type=click.IntRange(min=1),
        default=DEFAULT_MAX_WORKERS,
        )
@click.pass_context
def download(ctx, url: str, output: Path, jobs: int):
    """
    Download a Spotify track or playlist via URL as MP3 from YouTube
    """
    client_id = ctx.obj.get('client_id')
    redirect_uri = ctx.obj.get('redirect_uri')
    if TRACK_URL_HINT in url:
        print("Fetching track from Spotify…")
        track = get_track(url, client_id=client_id, redirect_uri=redirect_uri)
        assert track is not None

        _, matched = find_missing_tracks([track], output)
        if matched:
            _, local = matched[0]
            print(f"Skipping (already exists): {track.search_query()}")
            print(f"  ✓ {local.filepath}")
            return

        print(f"Downloading: {track.search_query()}")
        path = download_track(track, output_dir=output)
        if path is None:
            return
        print(f"  ✓ {path}")
    elif PLAYLIST_URL_HINT in url:
        print("Fetching playlist from Spotify…")
        tracks = get_playlist(url, client_id=client_id, redirect_uri=redirect_uri)
        print(f"Found {len(tracks)} track(s) in playlist.")

        missing, matched = find_missing_tracks(tracks, output)
        if matched:
            print(f"Skipping {len(matched)} track(s) already in {output}:")
            for _, local in matched:
                print(f"  ✓ {local.filepath}")

        if not missing:
            print("All tracks already downloaded.")
            return

        print(f"Starting download of {len(missing)} missing track(s)…")
        paths = download_tracks(missing, output_dir=output, max_workers=jobs)
        for path in paths:
            print(f"  ✓ {path}")
    else:
        print(
            "Error: URL must be a Spotify track or playlist URL.\n"
            "  Track:    https://open.spotify.com/track/<id>\n"
            "  Playlist: https://open.spotify.com/playlist/<id>",
            file=sys.stderr,
        )
        sys.exit(1)


cli.add_command(download)

if __name__ == '__main__':
    cli()
