"""Unit tests for zhuk.state."""

from zhuk.state import (
    PlaylistRecord,
    STATE_FILENAME,
    SyncState,
    load_state,
    save_state,
)


class TestLoadState:
    def test_missing_file_yields_empty_state(self, tmp_path):
        assert load_state(tmp_path).playlists == []

    def test_malformed_json_yields_empty_state(self, tmp_path):
        (tmp_path / STATE_FILENAME).write_text("not json{")
        assert load_state(tmp_path).playlists == []

    def test_non_dict_payload_yields_empty_state(self, tmp_path):
        (tmp_path / STATE_FILENAME).write_text("[1, 2, 3]")
        assert load_state(tmp_path).playlists == []

    def test_skips_entries_without_id_or_folder(self, tmp_path):
        (tmp_path / STATE_FILENAME).write_text(
            '{"version": 1, "playlists": ['
            '{"name": "no id"}, {"id": "x", "name": "no folder"},'
            '{"id": "ok", "name": "Fine", "folder": "Fine"}]}'
        )
        state = load_state(tmp_path)
        assert [r.id for r in state.playlists] == ["ok"]


class TestSaveState:
    def test_round_trips(self, tmp_path):
        state = SyncState()
        state.upsert(PlaylistRecord(id="id1", name="House", folder="House"))
        save_state(tmp_path, state)

        loaded = load_state(tmp_path)
        assert loaded.playlists == state.playlists

    def test_leaves_no_temp_file(self, tmp_path):
        save_state(tmp_path, SyncState())
        assert [p.name for p in tmp_path.iterdir()] == [STATE_FILENAME]


class TestSyncState:
    def test_upsert_replaces_by_id(self):
        state = SyncState()
        state.upsert(PlaylistRecord(id="a", name="Old", folder="Old"))
        state.upsert(PlaylistRecord(id="a", name="New", folder="New"))

        assert len(state.playlists) == 1
        assert state.playlists[0].name == "New"

    def test_record_for_and_selected_ids(self):
        state = SyncState([PlaylistRecord(id="a", name="A", folder="A")])
        assert state.record_for("a").name == "A"
        assert state.record_for("missing") is None
        assert state.selected_ids() == {"a"}
