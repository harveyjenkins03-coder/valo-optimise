# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
modules/auto_updater.py
=======================
In-app auto-updater for Valo Optimise.

Flow:
  1. check_for_update()   — background thread, queries GitHub Releases API
  2. download_update()    — background thread, streams new .exe with progress
  3. apply_update()       — writes a detached swap script, then caller quits
                            script waits for process exit → replaces exe → relaunches

Only activates when running as a frozen PyInstaller bundle (sys.frozen == True).
Falls back to browser download when running as a plain .py script.
Uses stdlib only — no extra dependencies.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser

try:
    from version import VERSION
except ImportError:
    VERSION = "1.0.0"

_GITHUB_REPO = "harveyjenkins03-coder/valo-optimise"
_API_URL      = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_ver(v: str) -> tuple:
    """'1.2.3' or 'v1.2.3'  →  (1, 2, 3)"""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


# ── Step 1 — Version check ─────────────────────────────────────────────────────

def check_for_update(on_update_available, on_current=None) -> None:
    """
    Query GitHub Releases API in a background thread.

    Calls  on_update_available(latest_ver, dl_url, page_url)  if a newer
    version exists.  dl_url is the direct .exe download link (may be None if
    the release has no attached asset — fallback to page_url in that case).

    Calls  on_current()  if already up to date, or on any network error.
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

            tag      = data.get("tag_name", "").lstrip("v")
            page_url = data.get("html_url", "")

            # Extract direct .exe download URL and expected SHA256 from release
            dl_url = None
            expected_sha256 = None
            for asset in data.get("assets", []):
                if asset.get("name", "").lower().endswith(".exe"):
                    dl_url = asset.get("browser_download_url")
                    break
            # Parse SHA256 from release body (format: "SHA256: <hex>")
            body = data.get("body", "") or ""
            sha_match = re.search(r"SHA256:\s*([a-fA-F0-9]{64})", body)
            if sha_match:
                expected_sha256 = sha_match.group(1).lower()

            if tag and _parse_ver(tag) > _parse_ver(VERSION):
                on_update_available(tag, dl_url, page_url, expected_sha256)
            elif on_current:
                on_current()

        except Exception:
            if on_current:
                on_current()

    threading.Thread(target=_check, daemon=True).start()


# ── Step 2 — Download ──────────────────────────────────────────────────────────

def download_update(dl_url: str, on_progress, on_complete, on_error,
                    expected_sha256: str = None) -> None:
    """
    Stream the new .exe to a temp file in a background thread.

    on_progress(bytes_done: int, total_bytes: int)  — called repeatedly
    on_complete(tmp_path: str)                       — called when fully written
    on_error(message: str)                           — called on failure
    expected_sha256: if provided, verify the download matches this hash
    """
    def _dl():
        try:
            # Place temp file next to the running exe so it's on the same drive
            # (move is instant when source and destination are on the same volume)
            if _is_frozen():
                tmp_dir = os.path.dirname(sys.executable)
            else:
                tmp_dir = tempfile.gettempdir()

            tmp_path = os.path.join(tmp_dir, "ValoOptimise_update.exe")

            req = urllib.request.Request(
                dl_url,
                headers={"User-Agent": f"ValoOptimise/{VERSION}"},
            )
            sha256 = hashlib.sha256()
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                done  = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)   # 64 KB
                        if not chunk:
                            break
                        f.write(chunk)
                        sha256.update(chunk)
                        done += len(chunk)
                        on_progress(done, total)

            # Verify SHA256 if expected hash was provided in release notes
            if expected_sha256:
                actual = sha256.hexdigest()
                if actual != expected_sha256:
                    os.remove(tmp_path)
                    on_error(f"SHA256 mismatch: expected {expected_sha256}, got {actual}")
                    return

            on_complete(tmp_path)

        except Exception as exc:
            on_error(str(exc))

    threading.Thread(target=_dl, daemon=True).start()


# ── Step 3 — Apply ─────────────────────────────────────────────────────────────

def apply_update(new_exe_path: str) -> None:
    """
    Replace the running .exe with new_exe_path and schedule a relaunch.

    Writes a small batch script to %TEMP% that:
      - Polls until our process exits
      - Moves the new .exe over the old one  (move /y is atomic on NTFS)
      - Relaunches with UAC elevation
      - Deletes itself

    The caller should call  root.destroy() / root.quit()  immediately after.

    No-op when not running as a frozen bundle (dev mode).
    """
    if not _is_frozen():
        return

    current_exe = sys.executable
    pid         = os.getpid()

    # Batch script — runs detached after app exits
    bat_path = os.path.join(tempfile.gettempdir(), f"vo_update_{os.urandom(8).hex()}.bat")
    script = (
        "@echo off\r\n"
        # Wait until our PID is gone (poll every second, give up after 30 s)
        "set /a tries=0\r\n"
        ":wait\r\n"
        f'tasklist /FI "PID eq {pid}" /NH 2>nul | findstr /I /C:"{pid}" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  set /a tries+=1\r\n"
        "  if %tries% lss 30 (timeout /t 1 /nobreak >nul && goto wait)\r\n"
        ")\r\n"
        # Replace exe (move is atomic within one drive)
        f'move /y "{new_exe_path}" "{current_exe}" >nul\r\n'
        # Relaunch elevated (RunAs verb)
        f'powershell -WindowStyle Hidden -Command "Start-Process '
        f"'{current_exe}'"
        f' -Verb RunAs"\r\n'
        # Self-destruct
        'del "%~f0"\r\n'
    )

    with open(bat_path, "w") as f:
        f.write(script)

    # Launch detached so it survives after we quit
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=(
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
        ),
        close_fds=True,
    )
