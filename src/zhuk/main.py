from pathlib import Path

import click

from zhuk.downloader import download_track, download_tracks
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
@click.pass_context
def download(ctx, url, output):
    """
    Download a Spotify track or playlist via URL as MP3 from YouTube
    """
    client_id = ctx.obj.get('client_id')
    redirect_uri = ctx.obj.get('redirect_uri')
    if TRACK_URL_HINT in url:
        print("Fetching track from Spotify…")
        track = get_track(url, client_id=client_id, redirect_uri=redirect_uri)
        assert track is not None
        print(f"Downloading: {track.search_query()}")
        path = download_track(track, output_dir=output)
        if path is None:
            return
        print(f"  ✓ {path}")
    elif PLAYLIST_URL_HINT in url:
        print("Fetching playlist from Spotify…")
        tracks = get_playlist(url, client_id=client_id, redirect_uri=redirect_uri)
        print(f"Found {len(tracks)} track(s) in playlist.")
        print("Starting download…")
        paths = download_tracks(tracks, output_dir=output)
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
