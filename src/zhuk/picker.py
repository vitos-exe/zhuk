"""Interactive playlist selection."""

from __future__ import annotations

import questionary

from zhuk.spotify import PlaylistInfo


def _label(playlist: PlaylistInfo) -> str:
    return f"{playlist.name} ({playlist.track_count} tracks)"


def select_playlists(
    playlists: list[PlaylistInfo], preselected: set[str] | None = None
) -> list[PlaylistInfo]:
    """Prompt the user to pick playlists to sync.

    Playlists already selected on a previous run start checked. Typing filters
    the list by name. Returns an empty list if the user aborts.
    """
    if not playlists:
        return []

    preselected = preselected or set()
    choices = [
        questionary.Choice(
            title=_label(playlist),
            value=playlist.id,
            checked=playlist.id in preselected,
        )
        for playlist in playlists
    ]

    selected_ids = questionary.checkbox(
        "Select playlists to sync (type to search, space to toggle, enter to confirm):",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    if not selected_ids:
        return []

    chosen = set(selected_ids)
    return [playlist for playlist in playlists if playlist.id in chosen]
