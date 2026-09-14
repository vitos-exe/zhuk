"""Mirror-sync selected Spotify playlists into per-playlist subfolders."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import click

from zhuk.downloader import DEFAULT_MAX_WORKERS, download_tracks
from zhuk.matcher import index_by_spotify_id, diff_playlist, scan_sync_files
from zhuk.naming import sanitize_name
from zhuk.playlist_file import M3U8_SUFFIX, write_m3u8
from zhuk.spotify import PlaylistInfo, TrackInfo, get_playlist
from zhuk.state import PlaylistRecord, SyncState

# Refuse to delete most of a folder without --force: that pattern almost always
# means a wrong target directory or an empty API response, not a real edit.
DELETION_RATIO_LIMIT = 0.8


@dataclass
class PlaylistPlan:
    """What a single playlist needs in order to match Spotify."""

    playlist: PlaylistInfo
    folder: Path
    tracks: list[TrackInfo] = field(default_factory=list)
    missing: list[TrackInfo] = field(default_factory=list)
    present: dict[str, Path] = field(default_factory=dict)
    orphans: list[Path] = field(default_factory=list)
    blocked_reason: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)


def folder_name_for(playlist: PlaylistInfo) -> str:
    """Return the subfolder name for *playlist*."""
    return sanitize_name(playlist.name)


def find_duplicate_names(playlists: list[PlaylistInfo]) -> dict[str, list[PlaylistInfo]]:
    """Group *playlists* whose sanitized names collide."""
    by_name: dict[str, list[PlaylistInfo]] = defaultdict(list)
    for playlist in playlists:
        by_name[folder_name_for(playlist)].append(playlist)
    return {name: group for name, group in by_name.items() if len(group) > 1}


def resolve_selection(
    playlists: list[PlaylistInfo], wanted: tuple[str, ...]
) -> tuple[list[PlaylistInfo], list[str]]:
    """Match *wanted* names or IDs against *playlists*.

    Returns ``(selected, unknown)``. Matching is case-insensitive on name and
    exact on ID.
    """
    selected: list[PlaylistInfo] = []
    unknown: list[str] = []

    for needle in wanted:
        match = next(
            (
                p
                for p in playlists
                if p.id == needle or p.name.lower() == needle.lower()
            ),
            None,
        )
        if match is None:
            unknown.append(needle)
        elif match not in selected:
            selected.append(match)

    return selected, unknown


def apply_folder_renames(
    target: Path, state: SyncState, playlists: list[PlaylistInfo], dry_run: bool = False
) -> list[tuple[str, str]]:
    """Rename folders whose playlist was renamed on Spotify.

    Returns the ``(old, new)`` pairs applied. A rename is skipped when the
    destination already exists, so nothing is ever overwritten.
    """
    renames: list[tuple[str, str]] = []

    for playlist in playlists:
        record = state.record_for(playlist.id)
        if record is None:
            continue

        new_folder = folder_name_for(playlist)
        if record.folder == new_folder:
            continue

        old_path = target / record.folder
        new_path = target / new_folder
        if not old_path.is_dir() or new_path.exists():
            continue

        if not dry_run:
            old_path.rename(new_path)
            # The playlist file is named after the playlist, and M3U8s are
            # protected from orphan deletion, so the stale one must go here or
            # it lingers forever and imports as a duplicate.
            stale = new_path / f"{record.folder}{M3U8_SUFFIX}"
            if stale.is_file():
                stale.unlink()
        renames.append((record.folder, new_folder))

    return renames


def build_plan(
    target: Path,
    playlist: PlaylistInfo,
    tracks: list[TrackInfo],
    force: bool = False,
) -> PlaylistPlan:
    """Diff *playlist* against its folder and apply the deletion interlock."""
    folder = target / folder_name_for(playlist)
    missing, present, orphans = diff_playlist(tracks, folder)

    plan = PlaylistPlan(
        playlist=playlist,
        folder=folder,
        tracks=tracks,
        missing=missing,
        present=present,
        orphans=orphans,
    )

    if orphans and not force:
        total = len(scan_sync_files(folder))
        if total and len(orphans) / total >= DELETION_RATIO_LIMIT:
            plan.blocked_reason = (
                f"would delete {len(orphans)} of {total} file(s) "
                f"({len(orphans) / total:.0%}); re-run with --force to allow"
            )

    return plan


def _describe(plan: PlaylistPlan) -> None:
    click.echo(f"\n{plan.playlist.name} -> {plan.folder}")
    click.echo(f"  {len(plan.tracks)} track(s) in playlist")
    click.echo(f"  {len(plan.present)} already downloaded")
    click.echo(f"  {len(plan.missing)} to download")
    click.echo(f"  {len(plan.orphans)} to delete")


def sync_playlists(
    target: Path,
    selected: list[PlaylistInfo],
    state: SyncState,
    client_id: str | None = None,
    redirect_uri: str | None = None,
    sp=None,
    jobs: int = DEFAULT_MAX_WORKERS,
    write_playlist_file: bool = True,
    dry_run: bool = False,
    assume_yes: bool = False,
    force: bool = False,
) -> int:
    """Sync *selected* playlists into *target*. Returns a process exit code."""
    target = Path(target)

    duplicates = find_duplicate_names(selected)
    skipped: list[str] = []
    if duplicates:
        conflicting = {p.id for group in duplicates.values() for p in group}
        for name, group in duplicates.items():
            names = ", ".join(p.id for p in group)
            click.echo(
                f"Skipping {len(group)} playlist(s) sharing the folder name "
                f"'{name}' ({names}). Rename one on Spotify to sync them.",
                err=True,
            )
            skipped.append(name)
        selected = [p for p in selected if p.id not in conflicting]

    if not selected:
        click.echo("Nothing to sync.")
        return 1 if skipped else 0

    for old, new in apply_folder_renames(target, state, selected, dry_run=dry_run):
        click.echo(f"Renamed folder '{old}' -> '{new}'")

    click.echo("Fetching playlist contents from Spotify…")
    plans: list[PlaylistPlan] = []
    for playlist in selected:
        tracks = get_playlist(
            playlist.id, client_id=client_id, redirect_uri=redirect_uri, sp=sp
        )
        plans.append(build_plan(target, playlist, tracks, force=force))

    for plan in plans:
        _describe(plan)
        if plan.blocked:
            click.echo(f"  ! refusing: {plan.blocked_reason}", err=True)

    deletions = [path for plan in plans if not plan.blocked for path in plan.orphans]

    if dry_run:
        click.echo("\nDry run: no files were downloaded, deleted or renamed.")
        return 0

    if deletions:
        click.echo(f"\nThe following {len(deletions)} file(s) will be DELETED:")
        for path in deletions:
            click.echo(f"  - {path}")
        if not assume_yes and not click.confirm("Delete these files?", default=False):
            click.echo("Aborted; nothing was changed.")
            return 1

    exit_code = 0
    for plan in plans:
        if plan.blocked:
            exit_code = 1
            continue

        click.echo(f"\n{plan.playlist.name}:")

        if plan.missing:
            click.echo(f"  downloading {len(plan.missing)} track(s)…")
            paths = download_tracks(plan.missing, output_dir=plan.folder, max_workers=jobs)
            click.echo(f"  ✓ downloaded {len(paths)} track(s)")
            if len(paths) < len(plan.missing):
                click.echo(
                    f"  ! {len(plan.missing) - len(paths)} track(s) could not be "
                    "downloaded; they will be retried next run",
                    err=True,
                )

        for path in plan.orphans:
            try:
                Path(path).unlink()
                click.echo(f"  ✗ deleted {path}")
            except OSError as exc:
                click.echo(f"  ! could not delete {path}: {exc}", err=True)
                exit_code = 1

        if write_playlist_file:
            local_paths, _ = index_by_spotify_id(plan.folder)
            m3u8 = write_m3u8(plan.folder, plan.playlist.name, plan.tracks, local_paths)
            click.echo(f"  ✓ wrote {m3u8}")

        state.upsert(
            PlaylistRecord(
                id=plan.playlist.id,
                name=plan.playlist.name,
                folder=folder_name_for(plan.playlist),
            )
        )

    if skipped:
        exit_code = 1

    return exit_code
