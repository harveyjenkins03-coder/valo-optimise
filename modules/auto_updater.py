"""
modules/auto_updater.py
=======================
Checks GitHub Releases for a newer version of Valo Optimise.
Runs entirely in a background thread — never blocks the GUI.
Uses stdlib only (urllib, json, threading).
"""
import urllib.request
import urllib.error
import json
import threading
import webbrowser

try:
    from version import VERSION
except ImportError:
    VERSION = "1.0.0"

_GITHUB_REPO = "harveyjenkins03-coder/valo-optimise"
_API_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"


def _parse_ver(v: str) -> tuple:
    """'1.2.3' or 'v1.2.3' → (1, 2, 3)"""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update(on_update_available, on_current=None) -> None:
    """
    Check GitHub for the latest release in a background thread.

    Calls on_update_available(latest_version_str, release_page_url)
    if a newer version is found.

    Calls on_current() (optional) if already up to date or on any error.
    """
    def _check():
        try:
            req = urllib.request.Request(
                _API_URL,
                headers={
                    "User-Agent": f"ValoOptimise/{VERSION}",
                    "Accept":     "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "").lstrip("v")
            url = data.get("html_url", "")
            if tag and _parse_ver(tag) > _parse_ver(VERSION):
                on_update_available(tag, url)
            elif on_current:
                on_current()
        except Exception:
            if on_current:
                on_current()

    threading.Thread(target=_check, daemon=True).start()


def open_download_page(url: str) -> None:
    """Open the GitHub release page in the user's browser."""
    try:
        webbrowser.open(url)
    except Exception:
        pass
