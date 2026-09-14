import sys
from pathlib import Path

import click

from zhuk.downloader import DEFAULT_MAX_WORKERS, download_track, download_tracks
from zhuk.matcher import find_missing_tracks
from zhuk.picker import select_playlists
from zhuk.spotify import build_client, get_playlist, get_track, list_playlists
from zhuk.state import load_state, save_state
from zhuk.sync import resolve_selection as _resolve_wanted, sync_playlists

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


@click.command()
@click.option(
        '-o',
        '--output',
        help="Directory holding one subfolder per playlist (default: downloads)",
        type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
        default=Path("downloads")
        )
@click.option(
        '-j',
        '--jobs',
        help="Number of tracks to download in parallel (default: 4)",
        type=click.IntRange(min=1),
        default=DEFAULT_MAX_WORKERS,
        )
@click.option('--select', is_flag=True, help="Reopen the playlist picker")
@click.option('--all', 'all_playlists', is_flag=True, help="Sync every playlist")
@click.option(
        '--playlist',
        'wanted',
        multiple=True,
        help="Playlist name or ID to sync; repeatable, implies non-interactive",
        )
@click.option('--no-playlist-file', is_flag=True, help="Do not write .m3u8 files")
@click.option('--dry-run', is_flag=True, help="Report what would change, alter nothing")
@click.option('--yes', 'assume_yes', is_flag=True, help="Skip the deletion confirmation")
@click.option('--force', is_flag=True, help="Allow deleting most of a folder")
@click.pass_context
def sync(
    ctx,
    output: Path,
    jobs: int,
    select: bool,
    all_playlists: bool,
    wanted: tuple[str, ...],
    no_playlist_file: bool,
    dry_run: bool,
    assume_yes: bool,
    force: bool,
):
    """
    Mirror your Spotify playlists into per-playlist subfolders.

    WARNING: this deletes local files that are no longer in a playlist.
    """
    client_id = ctx.obj.get('client_id')
    redirect_uri = ctx.obj.get('redirect_uri')

    output.mkdir(parents=True, exist_ok=True)

    sp = build_client(client_id, redirect_uri)

    print("Fetching your playlists from Spotify…")
    playlists = list_playlists(sp=sp)
    if not playlists:
        print("No playlists found for this account.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(playlists)} playlist(s).")

    state = load_state(output)
    stored_ids = state.selected_ids()

    if wanted:
        selected, unknown = _resolve_wanted(playlists, wanted)
        for needle in unknown:
            print(f"Warning: no playlist matched '{needle}'.", file=sys.stderr)
    elif all_playlists:
        selected = playlists
    elif select or not stored_ids:
        selected = select_playlists(playlists, preselected=stored_ids)
        if not selected:
            print("No playlists selected.")
            sys.exit(0)
    else:
        selected = [p for p in playlists if p.id in stored_ids]
        missing_ids = stored_ids - {p.id for p in selected}
        for playlist_id in sorted(missing_ids):
            print(
                f"Warning: previously selected playlist {playlist_id} is no longer "
                "available; skipping.",
                file=sys.stderr,
            )

    exit_code = sync_playlists(
        output,
        selected,
        state,
        client_id=client_id,
        redirect_uri=redirect_uri,
        sp=sp,
        jobs=jobs,
        write_playlist_file=not no_playlist_file,
        dry_run=dry_run,
        assume_yes=assume_yes,
        force=force,
    )

    if not dry_run:
        save_state(output, state)

    sys.exit(exit_code)


cli.add_command(download)
cli.add_command(sync)

if __name__ == '__main__':
    cli()
