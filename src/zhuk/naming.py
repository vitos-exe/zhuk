"""Filesystem-safe name generation for playlist folders and track filenames."""

from __future__ import annotations

import re

FALLBACK_NAME = "untitled"
MAX_NAME_LENGTH = 120

# Characters that are illegal on Windows/FAT32 or act as path separators.
# FAT32 matters here: DJ USB sticks are routinely formatted that way.
_ILLEGAL = r'<>:"/\\|?*'
_ILLEGAL_RE = re.compile(f"[{re.escape(_ILLEGAL)}]")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")

# Reserved device names on Windows; harmless elsewhere but cheap to avoid.
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def sanitize_name(name: str) -> str:
    """Return *name* reduced to a safe file or directory name.

    Illegal and control characters are replaced, whitespace is collapsed, and
    leading dots plus trailing dots and spaces are stripped so the result is
    never hidden, never reserved, and never empty.
    """
    if not name:
        return FALLBACK_NAME

    cleaned = _CONTROL_RE.sub("", name)
    cleaned = _ILLEGAL_RE.sub("-", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    # A leading dot would hide the file, and our sync allowlist skips dotfiles.
    cleaned = cleaned.lstrip(".").strip()
    # Trailing dots and spaces are silently dropped by Windows.
    cleaned = cleaned.rstrip(". ")

    if len(cleaned) > MAX_NAME_LENGTH:
        cleaned = cleaned[:MAX_NAME_LENGTH].rstrip(". ")

    if not cleaned or cleaned.lower() in _RESERVED:
        return FALLBACK_NAME

    return cleaned


def track_basename(artist: str, title: str) -> str:
    """Return the sanitized ``Artist - Title`` basename for a track, no extension."""
    artist = (artist or "").strip()
    title = (title or "").strip()

    if artist and title:
        raw = f"{artist} - {title}"
    else:
        raw = title or artist

    return sanitize_name(raw)
