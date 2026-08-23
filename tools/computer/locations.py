"""Shared helpers for resolving spoken locations to filesystem paths."""

import os
import re

_KNOWN_DIRS = {
    "desktop": lambda: _desktop_path(),
    "documents": lambda: os.path.join(os.path.expanduser("~"), "Documents"),
    "downloads": lambda: os.path.join(os.path.expanduser("~"), "Downloads"),
    "pictures": lambda: os.path.join(os.path.expanduser("~"), "Pictures"),
    "music": lambda: os.path.join(os.path.expanduser("~"), "Music"),
    "videos": lambda: os.path.join(os.path.expanduser("~"), "Videos"),
}

_DIR_PHRASE_RE = re.compile(
    r"\b(?:in|into|to|at|on|under|inside)\s+(?:the\s+)?"
    r"(desktop|documents?|downloads?|pictures?|music|videos?)\b", re.I)
_DRIVE_RE = re.compile(r"\b([c-z])\s*(?::\\?|drive)\b", re.I)


def _desktop_path():
    """Real Desktop folder, checking OneDrive first."""
    candidates = [
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("HOMEPATH", ""), "Desktop"),
    ]
    for p in candidates:
        if p and os.path.isdir(p):
            return p
    return os.path.join(os.path.expanduser("~"), "Desktop")


def base_for(name):
    """Path for a known dir name ('desktop'), or None."""
    fn = _KNOWN_DIRS.get(name.lower().rstrip("s"))
    return fn() if fn else None


def extract_location(text):
    """Find a spoken location in text. Returns (label, base_path) or None."""
    m = _DIR_PHRASE_RE.search(text)
    if m:
        label = m.group(1).lower()
        base = base_for(label)
        if base:
            return label, base
    m = _DRIVE_RE.search(text)
    if m:
        drive = m.group(1).upper()
        return f"{drive} drive", f"{drive}:\\"
    return None


def looks_like_location_answer(text):
    """True when a short reply is essentially just a location."""
    t = text.strip().lower()
    if not t or len(t) > 40:
        return False
    if t in {k for k in _KNOWN_DIRS} | {k + "s" for k in _KNOWN_DIRS}:
        return True
    if extract_location(t):
        return True
    # bare absolute path pasted back
    return bool(re.match(r"^[a-z]:\\[\w\\\s.\-]+$", t))