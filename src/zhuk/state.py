"""Persisted sync state stored as ``.zhuk.json`` at the target root."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATE_FILENAME = ".zhuk.json"
STATE_VERSION = 1


@dataclass
class PlaylistRecord:
    """A playlist previously selected for syncing, and the folder it lives in."""

    id: str
    name: str
    folder: str


@dataclass
class SyncState:
    """Everything the sync remembers between runs."""

    playlists: list[PlaylistRecord] = field(default_factory=list)

    def record_for(self, playlist_id: str) -> PlaylistRecord | None:
        """Return the stored record for *playlist_id*, or None if unknown."""
        for record in self.playlists:
            if record.id == playlist_id:
                return record
        return None

    def selected_ids(self) -> set[str]:
        """Return the set of playlist IDs selected on a previous run."""
        return {record.id for record in self.playlists}

    def upsert(self, record: PlaylistRecord) -> None:
        """Insert *record*, replacing any existing record with the same ID."""
        for index, existing in enumerate(self.playlists):
            if existing.id == record.id:
                self.playlists[index] = record
                return
        self.playlists.append(record)


def state_path(target: Path) -> Path:
    """Return the path of the state file for *target*."""
    return Path(target) / STATE_FILENAME


def load_state(target: Path) -> SyncState:
    """Load sync state from *target*.

    A missing, unreadable or malformed state file yields empty state rather than
    an error: losing the selection is recoverable, refusing to run is not.
    """
    path = state_path(target)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SyncState()

    if not isinstance(raw, dict):
        return SyncState()

    records: list[PlaylistRecord] = []
    for entry in raw.get("playlists") or []:
        if not isinstance(entry, dict):
            continue
        playlist_id = entry.get("id")
        folder = entry.get("folder")
        if not playlist_id or not folder:
            continue
        records.append(
            PlaylistRecord(
                id=str(playlist_id),
                name=str(entry.get("name") or ""),
                folder=str(folder),
            )
        )

    return SyncState(playlists=records)


def save_state(target: Path, state: SyncState) -> None:
    """Write *state* to *target* atomically."""
    path = state_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": STATE_VERSION,
        "playlists": [asdict(record) for record in state.playlists],
    }

    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
