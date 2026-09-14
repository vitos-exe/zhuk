"""Unit tests for zhuk.sync."""

from unittest.mock import patch

from zhuk.spotify import PlaylistInfo, TrackInfo
from zhuk.state import PlaylistRecord, SyncState
from zhuk.sync import (
    apply_folder_renames,
    build_plan,
    find_duplicate_names,
    resolve_selection,
    sync_playlists,
)


def _track(spotify_id, title=None):
    return TrackInfo(
        title=title or f"Song {spotify_id}", artist="Artist", spotify_id=spotify_id
    )


def _playlist(playlist_id="p1", name="House", count=0):
    return PlaylistInfo(id=playlist_id, name=name, track_count=count)


class TestFindDuplicateNames:
    def test_detects_collision(self):
        duplicates = find_duplicate_names([_playlist("a", "House"), _playlist("b", "House")])
        assert list(duplicates) == ["House"]

    def test_detects_collision_after_sanitization(self):
        duplicates = find_duplicate_names(
            [_playlist("a", "House/Techno"), _playlist("b", "House-Techno")]
        )
        assert list(duplicates) == ["House-Techno"]

    def test_no_collision(self):
        assert find_duplicate_names([_playlist("a", "House"), _playlist("b", "Techno")]) == {}


class TestResolveSelection:
    def test_matches_by_id_and_name_case_insensitively(self):
        playlists = [_playlist("a", "House"), _playlist("b", "Techno")]
        selected, unknown = resolve_selection(playlists, ("a", "techno"))

        assert [p.id for p in selected] == ["a", "b"]
        assert unknown == []

    def test_reports_unknown(self):
        selected, unknown = resolve_selection([_playlist("a", "House")], ("nope",))
        assert selected == []
        assert unknown == ["nope"]

    def test_deduplicates(self):
        playlists = [_playlist("a", "House")]
        selected, _ = resolve_selection(playlists, ("a", "House"))
        assert len(selected) == 1


class TestApplyFolderRenames:
    def test_renames_folder_when_playlist_renamed(self, tmp_path):
        (tmp_path / "Old Name").mkdir()
        state = SyncState([PlaylistRecord(id="p1", name="Old Name", folder="Old Name")])

        renames = apply_folder_renames(tmp_path, state, [_playlist("p1", "New Name")])

        assert renames == [("Old Name", "New Name")]
        assert (tmp_path / "New Name").is_dir()
        assert not (tmp_path / "Old Name").exists()

    def test_dry_run_does_not_touch_disk(self, tmp_path):
        (tmp_path / "Old Name").mkdir()
        state = SyncState([PlaylistRecord(id="p1", name="Old Name", folder="Old Name")])

        apply_folder_renames(tmp_path, state, [_playlist("p1", "New Name")], dry_run=True)

        assert (tmp_path / "Old Name").is_dir()

    def test_never_overwrites_existing_destination(self, tmp_path):
        (tmp_path / "Old Name").mkdir()
        (tmp_path / "New Name").mkdir()
        state = SyncState([PlaylistRecord(id="p1", name="Old Name", folder="Old Name")])

        assert apply_folder_renames(tmp_path, state, [_playlist("p1", "New Name")]) == []
        assert (tmp_path / "Old Name").is_dir()

    def test_ignores_unknown_playlists(self, tmp_path):
        assert apply_folder_renames(tmp_path, SyncState(), [_playlist("p1", "House")]) == []


class TestBuildPlan:
    def test_classifies_missing_present_and_orphans(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        make_mp3(folder / "keep.mp3", spotify_id="id1")
        make_mp3(folder / "gone.mp3", spotify_id="id2")

        plan = build_plan(tmp_path, _playlist(name="House"), [_track("id1"), _track("id3")])

        assert [t.spotify_id for t in plan.missing] == ["id3"]
        assert set(plan.present) == {"id1"}
        assert [p.name for p in plan.orphans] == ["gone.mp3"]

    def test_untagged_files_are_orphans(self, tmp_path, make_mp3):
        # Clean-slate behaviour: files with no embedded Spotify ID are not ours.
        folder = tmp_path / "House"
        make_mp3(folder / "legacy.mp3", spotify_id=None)
        make_mp3(folder / "a.mp3", spotify_id="id1")
        make_mp3(folder / "b.mp3", spotify_id="id2")

        plan = build_plan(tmp_path, _playlist(name="House"), [_track("id1"), _track("id2")])

        assert [p.name for p in plan.orphans] == ["legacy.mp3"]

    def test_protected_files_are_never_orphans(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        make_mp3(folder / "a.mp3", spotify_id="id1")
        (folder / "House.m3u8").write_text("#EXTM3U\n")
        (folder / ".DS_Store").write_text("junk")
        (folder / ".zhuk.json").write_text("{}")

        plan = build_plan(tmp_path, _playlist(name="House"), [_track("id1")])

        assert plan.orphans == []

    def test_blocks_when_deleting_most_of_folder(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"old{i}.mp3", spotify_id=f"old{i}")

        plan = build_plan(tmp_path, _playlist(name="House"), [_track("new")])

        assert plan.blocked
        assert "--force" in plan.blocked_reason

    def test_force_overrides_the_interlock(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"old{i}.mp3", spotify_id=f"old{i}")

        plan = build_plan(tmp_path, _playlist(name="House"), [_track("new")], force=True)

        assert not plan.blocked

    def test_empty_playlist_is_blocked(self, tmp_path, make_mp3):
        # An empty API response must never silently wipe a folder.
        folder = tmp_path / "House"
        make_mp3(folder / "a.mp3", spotify_id="id1")

        plan = build_plan(tmp_path, _playlist(name="House"), [])

        assert plan.blocked

    def test_small_deletion_is_not_blocked(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"keep{i}.mp3", spotify_id=f"id{i}")
        make_mp3(folder / "gone.mp3", spotify_id="stale")

        tracks = [_track(f"id{i}") for i in range(5)]
        plan = build_plan(tmp_path, _playlist(name="House"), tracks)

        assert not plan.blocked
        assert [p.name for p in plan.orphans] == ["gone.mp3"]


class TestSyncPlaylists:
    def test_downloads_missing_and_deletes_orphans(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"keep{i}.mp3", spotify_id=f"id{i}")
        make_mp3(folder / "gone.mp3", spotify_id="stale")

        tracks = [_track(f"id{i}") for i in range(5)] + [_track("new")]
        state = SyncState()

        with patch("zhuk.sync.get_playlist", return_value=tracks), patch(
            "zhuk.sync.download_tracks", return_value=[]
        ) as mock_download:
            code = sync_playlists(
                tmp_path, [_playlist(name="House")], state, assume_yes=True
            )

        assert code == 0
        assert not (folder / "gone.mp3").exists()
        assert (folder / "keep0.mp3").exists()
        assert [t.spotify_id for t in mock_download.call_args[0][0]] == ["new"]

    def test_declining_confirmation_changes_nothing(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"keep{i}.mp3", spotify_id=f"id{i}")
        make_mp3(folder / "gone.mp3", spotify_id="stale")

        tracks = [_track(f"id{i}") for i in range(5)]

        with patch("zhuk.sync.get_playlist", return_value=tracks), patch(
            "zhuk.sync.download_tracks", return_value=[]
        ) as mock_download, patch("zhuk.sync.click.confirm", return_value=False):
            code = sync_playlists(tmp_path, [_playlist(name="House")], SyncState())

        assert code == 1
        assert (folder / "gone.mp3").exists()
        mock_download.assert_not_called()

    def test_dry_run_changes_nothing(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"keep{i}.mp3", spotify_id=f"id{i}")
        make_mp3(folder / "gone.mp3", spotify_id="stale")

        tracks = [_track(f"id{i}") for i in range(5)] + [_track("new")]

        with patch("zhuk.sync.get_playlist", return_value=tracks), patch(
            "zhuk.sync.download_tracks"
        ) as mock_download:
            code = sync_playlists(
                tmp_path, [_playlist(name="House")], SyncState(), dry_run=True
            )

        assert code == 0
        assert (folder / "gone.mp3").exists()
        mock_download.assert_not_called()
        assert not list(folder.glob("*.m3u8"))

    def test_blocked_playlist_is_left_alone(self, tmp_path, make_mp3):
        folder = tmp_path / "House"
        for i in range(5):
            make_mp3(folder / f"old{i}.mp3", spotify_id=f"old{i}")

        with patch("zhuk.sync.get_playlist", return_value=[_track("new")]), patch(
            "zhuk.sync.download_tracks", return_value=[]
        ) as mock_download:
            code = sync_playlists(
                tmp_path, [_playlist(name="House")], SyncState(), assume_yes=True
            )

        assert code == 1
        assert (folder / "old0.mp3").exists()
        mock_download.assert_not_called()

    def test_duplicate_names_skip_only_conflicting_playlists(self, tmp_path, make_mp3):
        make_mp3(tmp_path / "Techno" / "a.mp3", spotify_id="id1")

        selected = [
            _playlist("a", "House"),
            _playlist("b", "House"),
            _playlist("c", "Techno"),
        ]
        state = SyncState()

        with patch("zhuk.sync.get_playlist", return_value=[_track("id1")]) as mock_get, patch(
            "zhuk.sync.download_tracks", return_value=[]
        ):
            code = sync_playlists(tmp_path, selected, state, assume_yes=True)

        assert code == 1
        # Only the non-conflicting playlist was fetched and recorded.
        assert mock_get.call_count == 1
        assert [r.id for r in state.playlists] == ["c"]

    def test_writes_playlist_file_and_state(self, tmp_path, make_mp3):
        make_mp3(tmp_path / "House" / "a.mp3", spotify_id="id1")
        state = SyncState()

        with patch("zhuk.sync.get_playlist", return_value=[_track("id1")]), patch(
            "zhuk.sync.download_tracks", return_value=[]
        ):
            sync_playlists(tmp_path, [_playlist(name="House")], state, assume_yes=True)

        assert (tmp_path / "House" / "House.m3u8").exists()
        assert state.record_for("p1").folder == "House"

    def test_no_playlist_file_option(self, tmp_path, make_mp3):
        make_mp3(tmp_path / "House" / "a.mp3", spotify_id="id1")

        with patch("zhuk.sync.get_playlist", return_value=[_track("id1")]), patch(
            "zhuk.sync.download_tracks", return_value=[]
        ):
            sync_playlists(
                tmp_path,
                [_playlist(name="House")],
                SyncState(),
                assume_yes=True,
                write_playlist_file=False,
            )

        assert not list((tmp_path / "House").glob("*.m3u8"))

    def test_nothing_selected(self, tmp_path):
        assert sync_playlists(tmp_path, [], SyncState()) == 0


class TestRenameCleansUpStalePlaylistFile:
    def test_removes_old_named_m3u8(self, tmp_path):
        folder = tmp_path / "Old Name"
        folder.mkdir()
        (folder / "Old Name.m3u8").write_text("#EXTM3U\n")
        (folder / "Handmade.m3u8").write_text("#EXTM3U\n")
        state = SyncState([PlaylistRecord(id="p1", name="Old Name", folder="Old Name")])

        apply_folder_renames(tmp_path, state, [_playlist("p1", "New Name")])

        new_folder = tmp_path / "New Name"
        assert not (new_folder / "Old Name.m3u8").exists()
        # Only the playlist file we own is removed.
        assert (new_folder / "Handmade.m3u8").exists()

    def test_dry_run_keeps_stale_file(self, tmp_path):
        folder = tmp_path / "Old Name"
        folder.mkdir()
        (folder / "Old Name.m3u8").write_text("#EXTM3U\n")
        state = SyncState([PlaylistRecord(id="p1", name="Old Name", folder="Old Name")])

        apply_folder_renames(tmp_path, state, [_playlist("p1", "New Name")], dry_run=True)

        assert (folder / "Old Name.m3u8").exists()
