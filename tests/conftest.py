"""Shared test fixtures."""

import pytest

# Click reads these via envvar=..., so a developer's real Spotify credentials
# would otherwise leak into CLI tests and break assertions on the parsed args.
SPOTIFY_ENV_VARS = ("SPOTIPY_CLIENT_ID", "SPOTIPY_REDIRECT_URI")


@pytest.fixture(autouse=True)
def clear_spotify_env(monkeypatch):
    for name in SPOTIFY_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_mp3():
    """Return a factory writing a stub MP3 carrying real ID3 tags."""
    import mutagen.id3

    def _make(path, title="Title", artist="Artist", spotify_id=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        tags = mutagen.id3.ID3()
        tags["TIT2"] = mutagen.id3.TIT2(encoding=3, text=title)
        tags["TPE1"] = mutagen.id3.TPE1(encoding=3, text=artist)
        if spotify_id is not None:
            tags["TXXX:SPOTIFY_TRACK_ID"] = mutagen.id3.TXXX(
                encoding=3, desc="SPOTIFY_TRACK_ID", text=spotify_id
            )
        tags.save(path)
        return path

    return _make
