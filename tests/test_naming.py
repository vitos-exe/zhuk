"""Unit tests for zhuk.naming."""

from zhuk.naming import FALLBACK_NAME, MAX_NAME_LENGTH, sanitize_name, track_basename


class TestSanitizeName:
    def test_keeps_ordinary_names(self):
        assert sanitize_name("Deep House") == "Deep House"

    def test_replaces_path_separators(self):
        assert "/" not in sanitize_name("House/Techno")
        assert "\\" not in sanitize_name("House\\Techno")

    def test_replaces_illegal_characters(self):
        result = sanitize_name('A:B"C|D?E*F<G>H')
        for char in ':"|?*<>':
            assert char not in result

    def test_strips_leading_dots(self):
        # A leading dot would hide the folder and the sync allowlist skips dotfiles.
        assert not sanitize_name("...hidden").startswith(".")

    def test_strips_trailing_dots_and_spaces(self):
        assert sanitize_name("Trailing. ") == "Trailing"

    def test_collapses_whitespace(self):
        assert sanitize_name("  a   b  ") == "a b"

    def test_removes_control_characters(self):
        assert sanitize_name("a\x00b\x1fc") == "abc"

    def test_empty_falls_back(self):
        assert sanitize_name("") == FALLBACK_NAME
        assert sanitize_name("   ") == FALLBACK_NAME
        assert sanitize_name("...") == FALLBACK_NAME

    def test_reserved_names_fall_back(self):
        assert sanitize_name("CON") == FALLBACK_NAME
        assert sanitize_name("lpt1") == FALLBACK_NAME

    def test_caps_length(self):
        assert len(sanitize_name("x" * 500)) == MAX_NAME_LENGTH

    def test_preserves_unicode(self):
        assert sanitize_name("Trap 🔥") == "Trap 🔥"


class TestTrackBasename:
    def test_combines_artist_and_title(self):
        assert track_basename("Daft Punk", "Da Funk") == "Daft Punk - Da Funk"

    def test_falls_back_to_title_only(self):
        assert track_basename("", "Only Title") == "Only Title"

    def test_falls_back_to_artist_only(self):
        assert track_basename("Only Artist", "") == "Only Artist"

    def test_sanitizes_result(self):
        assert "/" not in track_basename("AC/DC", "T.N.T")
