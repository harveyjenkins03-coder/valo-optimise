# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
utils/compat.py — Windows compatibility helpers for Valo Optimise
=================================================================
• DPI awareness (crisp rendering on high-DPI / scaled displays)
• Windows version detection (10 vs 11, build number)
• Input sanitisation (strips dangerous characters before registry/subprocess use)
• Session-resource helpers (CPU-affinity guard, lightweight polling gate)

All functions fail silently — callers never need to handle compat errors.
"""

import sys
import ctypes
import os
import re


# ── DPI Awareness ─────────────────────────────────────────────────────────────

def set_dpi_awareness() -> None:
    """
    Enables Per-Monitor DPI v2 awareness so CustomTkinter renders crisp text
    on 125 %, 150 %, or 200 % display-scaled monitors.

    Must be called BEFORE creating any Tk/CTk window.

    Falls back gracefully through three APIs (oldest to newest):
      1. SetProcessDPIAware        (Vista+)
      2. SetProcessDpiAwareness(2) (Win 8.1+, shcore.dll)
      3. SetProcessDpiAwarenessContext(-4) (Win 10 1703+, user32.dll)
    """
    try:
        # Best: Per-Monitor v2 (Win 10 Creators Update+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_ssize_t(-4)   # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        return
    except Exception:
        pass
    try:
        # Good: Per-Monitor v1 (Win 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        # Fallback: System-DPI aware (Vista+)
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ── Windows Version ───────────────────────────────────────────────────────────

def get_windows_version() -> tuple:
    """
    Returns (major, minor, build) e.g. (10, 0, 22621) for Windows 11 22H2.
    Returns (0, 0, 0) if detection fails.
    """
    try:
        v = sys.getwindowsversion()
        return (v.major, v.minor, v.build)
    except Exception:
        return (0, 0, 0)


def is_windows_11() -> bool:
    major, _, build = get_windows_version()
    return major == 10 and build >= 22_000


def is_windows_10() -> bool:
    major, _, build = get_windows_version()
    return major == 10 and build < 22_000


def get_version_display() -> str:
    """Returns a short human-readable string, e.g. 'Windows 11' or 'Windows 10'."""
    major, _, build = get_windows_version()
    if major == 10 and build >= 22_000:
        return "Windows 11"
    elif major == 10:
        return "Windows 10"
    elif major == 0:
        return "Windows"
    return f"Windows {major}"


# ── Input Sanitisation ────────────────────────────────────────────────────────

# Characters that must never appear in values passed to registry writes or
# subprocess arguments.  We allow printable ASCII + common Unicode but strip
# anything that could form a shell injection or path-traversal payload.
_DANGEROUS_RE = re.compile(
    r'[\x00-\x1f\x7f'          # control characters
    r'`$|&;<>(){}\\\'\"'        # shell metacharacters
    r'\.\./]',                  # path traversal fragments
    re.UNICODE,
)

def sanitize_input(text: str, max_len: int = 256) -> str:
    """
    Strips dangerous characters and truncates user-supplied text before it is
    used in subprocess arguments, registry values, or file paths.

    Safe for:  Riot ID lookup, profile names, any CTkEntry value.
    """
    if not isinstance(text, str):
        return ""
    # Remove null bytes and control characters
    cleaned = _DANGEROUS_RE.sub("", text)
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    # Truncate
    return cleaned[:max_len]


def sanitize_riot_id(riot_id: str) -> str:
    """
    Stricter sanitisation for Riot IDs (Name#TAG format).
    Allows only alphanumerics, spaces, hyphens, dots, and the # separator.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9 \-\.#]", "", riot_id.strip())
    return cleaned[:64]


# ── Session Resource Gate ─────────────────────────────────────────────────────

class TickerGate:
    """
    Lightweight guard that stops a repeating `after()` ticker from firing
    while the associated frame is hidden (not the active tab).

    Usage in a CTkFrame:
        self._gate = TickerGate()
        # when frame becomes visible:
        self._gate.open()
        # when frame is hidden:
        self._gate.close()
        # in the tick function:
        if not self._gate.is_open:
            return
    """
    __slots__ = ("is_open",)

    def __init__(self, start_open: bool = False):
        self.is_open = start_open

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False
