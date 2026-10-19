"""ANSI cleaning, one rule for every capture (tui_smoke and the probes).

The strip covers what a pty capture of pi 1.3.0 emits: CSI sequences including
private modes (cursor/scroll/wheel reporting), OSC sequences terminated by BEL
or ST, charset designation/shift escapes, and the bare ESC. Plain text passes
through untouched. Every offset into a CLEANED capture is char-based: take it
from len(clean(buf)), never len(buf) — a byte offset into a cleaned string
slice misses (that exact bug cost a false failing battery run).
"""
import re

_CSI = r"\[[0-9;?]*[a-zA-Z]"
_OSC = r"\][^\x07\x1b]*(?:\x07|\x1b\\)"
_CHARSET = r"[()][A-Z0-9]"
_STANDALONE = r"[=>]"
ANSI_RE = re.compile(rf"\x1b(?:{_CSI}|{_OSC}|{_CHARSET}|{_STANDALONE})")


def clean(x: bytes | str) -> str:
    t = x.decode("utf-8", "replace") if isinstance(x, bytes) else x
    return ANSI_RE.sub("", t)


def flat(x: bytes | str) -> str:
    """clean + all whitespace removed: for substring checks immune to wrapping."""
    return re.sub(r"\s", "", clean(x))


def advance(marker_len: int, buf: bytes | str) -> int:
    """Char offset of the current end of the cleaned capture, to slice later frames."""
    return len(clean(buf))
