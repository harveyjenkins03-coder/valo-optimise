# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
benchmark.py — Competitive Readiness Benchmark for Valo Optimise
=================================================================
Collects 12 OS-level performance metrics, computes a 0-100 score,
and supports before/after snapshots to prove measurable improvement.

All reads are non-destructive registry queries, WinAPI calls, and
subprocess invocations of standard Windows tools.  No game process
interaction — fully Vanguard-safe.
"""

import os
import json
import time
import socket
import ctypes
import winreg
import datetime
import subprocess
import psutil

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SNAP_FILE = os.path.join(_ROOT, "benchmark_snapshot.json")

# ── Metric metadata ──────────────────────────────────────────────────────────

_LABELS = {
    "timer_res":     "Timer Resolution",
    "core_parking":  "CPU Core Parking",
    "power_plan":    "Power Plan",
    "mouse_accel":   "Mouse Acceleration",
    "val_ping":      "Best Server Ping",
    "visual_fx":     "Visual Effects",
    "game_mode":     "Windows Game Mode",
    "bg_processes":  "Background Apps",
    "spatial_sound": "Spatial Sound",
    "cpu_boost":     "CPU Boost Mode",
    "ram_free":      "Available RAM",
    "startup_count": "Startup Programs",
}

_ICONS = {
    "timer_res":     "⏱️",
    "core_parking":  "🔲",
    "power_plan":    "⚡",
    "mouse_accel":   "🖱️",
    "val_ping":      "📡",
    "visual_fx":     "🖥️",
    "game_mode":     "🎮",
    "bg_processes":  "🧹",
    "spatial_sound": "🔊",
    "cpu_boost":     "🚀",
    "ram_free":      "🧠",
    "startup_count": "🗂️",
}

# Each weight is its % contribution toward 100 points total
_WEIGHTS = {
    "timer_res":     12,
    "core_parking":  12,
    "power_plan":    12,
    "mouse_accel":   10,
    "val_ping":       8,
    "cpu_boost":      8,
    "visual_fx":      8,
    "game_mode":      8,
    "bg_processes":   8,
    "spatial_sound":  6,
    "ram_free":       4,
    "startup_count":  4,
}

_IMPACT = {
    "timer_res":     "HIGH",
    "core_parking":  "HIGH",
    "power_plan":    "HIGH",
    "mouse_accel":   "HIGH",
    "val_ping":      "HIGH",
    "cpu_boost":     "HIGH",
    "visual_fx":     "MEDIUM",
    "game_mode":     "MEDIUM",
    "bg_processes":  "MEDIUM",
    "spatial_sound": "MEDIUM",
    "ram_free":      "LOW",
    "startup_count": "LOW",
}

_OPTIMAL_DESC = {
    "timer_res":     "≤ 1.5 ms",
    "core_parking":  "Unparked (100%)",
    "power_plan":    "High / Ultimate",
    "mouse_accel":   "Disabled",
    "val_ping":      "< 50 ms",
    "visual_fx":     "Best Performance",
    "game_mode":     "Enabled",
    "bg_processes":  "0 running",
    "spatial_sound": "Off",
    "cpu_boost":     "Enabled",
    "ram_free":      "≥ 4 GB free",
    "startup_count": "< 5 entries",
}

_WHY = {
    "timer_res":     "Controls frame-pacing precision and input-polling accuracy. Default is 15.6 ms.",
    "core_parking":  "Prevents CPU cores sleeping mid-fight — eliminates micro-stutter on burst load.",
    "power_plan":    "Determines how fast the CPU ramps from idle to full speed under game load.",
    "mouse_accel":   "Ensures 1:1 mouse-to-crosshair movement — no acceleration curve affecting aim.",
    "val_ping":      "Time from click to server registration. Every millisecond counts in gunfights.",
    "visual_fx":     "Frees GPU cycles wasted on UI animations — more frames available for the game.",
    "game_mode":     "Windows de-prioritises background tasks while a game is running.",
    "bg_processes":  "Fewer background apps = more CPU and RAM headroom reserved for Valorant.",
    "spatial_sound": "Windows Sonic interferes with Valorant's built-in HRTF positional audio.",
    "cpu_boost":     "Turbo Boost keeps clock speed high during the burst loads of combat.",
    "ram_free":      "Available RAM prevents disk paging and mid-fight stutters.",
    "startup_count": "Fewer autostart programs = cleaner system state at every session.",
}

# Order in which metrics are displayed
METRIC_ORDER = [
    "timer_res", "core_parking", "power_plan", "mouse_accel",
    "val_ping", "cpu_boost", "visual_fx", "game_mode",
    "bg_processes", "spatial_sound", "ram_free", "startup_count",
]


# ── Background-process targets ────────────────────────────────────────────────

_BG_TARGETS = {
    "onedrive.exe", "dropbox.exe", "googledrivesync.exe",
    "teams.exe", "slack.exe", "zoom.exe", "spotify.exe",
    "skype.exe", "telegram.exe", "whatsapp.exe",
    "searchindexer.exe", "searchprotocolhost.exe",
    "gamebar.exe", "xboxsocialappguest.exe",
    "cortana.exe", "widgets.exe",
}

# Protected startup paths (never flag as "too many" — Riot/Windows critical)
_PROTECTED_STARTUP = (
    "\\windows\\system32\\",
    "\\windows\\syswow64\\",
    "\\riot vanguard\\",
    "\\riot games\\",
)


# ─────────────────────────────────────────────────────────────────────────────

class SystemBenchmark:
    """Collects metrics, scores them, and manages before/after snapshots."""

    # ── Individual collectors ─────────────────────────────────────────────────

    def _get_timer_res(self) -> dict:
        try:
            min_res = ctypes.c_ulong(0)
            max_res = ctypes.c_ulong(0)
            cur_res = ctypes.c_ulong(0)
            ctypes.windll.ntdll.NtQueryTimerResolution(
                ctypes.byref(min_res), ctypes.byref(max_res), ctypes.byref(cur_res)
            )
            ms = cur_res.value / 10_000.0
            passed = ms <= 1.5
            display = f"{ms:.2f} ms"
        except Exception:
            ms = -1.0
            passed = False
            display = "Unknown"
        return {"key": "timer_res", "value": display, "raw": ms, "passed": passed}

    def _get_core_parking(self) -> dict:
        try:
            result = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES"],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            ac_val = None
            for line in result.stdout.lower().split("\n"):
                if "current ac power setting index" in line and "0x" in line:
                    try:
                        ac_val = int(line.split("0x")[1].strip(), 16)
                    except (ValueError, IndexError):
                        pass
                    break
            if ac_val is None:
                display, passed = "Unknown", False
            elif ac_val >= 100:
                display, passed = "Unparked (100%)", True
            elif ac_val == 0:
                display, passed = "Parked (0%)", False
            else:
                display, passed = f"Partial ({ac_val}%)", False
        except Exception:
            display, passed = "Unknown", False
        return {"key": "core_parking", "value": display, "passed": passed}

    def _get_power_plan(self) -> dict:
        try:
            result = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=6,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            text = result.stdout.lower()
            if "ultimate" in text:
                display, passed = "Ultimate Performance", True
            elif "high performance" in text or "high perf" in text:
                display, passed = "High Performance", True
            elif "balanced" in text:
                display, passed = "Balanced", False
            elif "power saver" in text:
                display, passed = "Power Saver", False
            else:
                import re
                m = re.search(r'\(([^)]+)\)', result.stdout)
                display = m.group(1).title() if m else "Unknown"
                passed = False
        except Exception:
            display, passed = "Unknown", False
        return {"key": "power_plan", "value": display, "passed": passed}

    def _get_mouse_accel(self) -> dict:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse",
                0, winreg.KEY_READ
            ) as k:
                val, _ = winreg.QueryValueEx(k, "MouseSpeed")
            passed = str(val) == "0"
            display = "Disabled" if passed else "Enabled"
        except Exception:
            display, passed = "Unknown", False
        return {"key": "mouse_accel", "value": display, "passed": passed}

    def _get_val_ping(self) -> dict:
        """TCP-connect to all Valorant game-server IPs, return best result."""
        servers = [
            ("206.165.102.1",  80),   # NA  US-East
            ("185.50.104.201", 80),   # EU  Frankfurt
            ("45.77.204.130",  80),   # AP  Singapore
            ("45.77.31.235",   80),   # KR  Seoul
            ("108.61.170.60",  80),   # LATAM Miami
        ]
        best_ms = 9_999.0
        for host, port in servers:
            try:
                t0 = time.perf_counter()
                s = socket.create_connection((host, port), timeout=2)
                t1 = time.perf_counter()
                s.close()
                ms = (t1 - t0) * 1_000
                if ms < best_ms:
                    best_ms = ms
            except Exception:
                pass
        if best_ms < 9_999:
            display = f"{best_ms:.0f} ms"
            passed = best_ms < 50
        else:
            display = "No connection"
            passed = False
        return {"key": "val_ping", "value": display, "raw": best_ms, "passed": passed}

    def _get_visual_fx(self) -> dict:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects",
                0, winreg.KEY_READ,
            ) as k:
                val, _ = winreg.QueryValueEx(k, "VisualFXSetting")
            passed = (val == 2)
            display = {
                0: "Let Windows Choose",
                1: "Best Appearance",
                2: "Best Performance",
                3: "Custom",
            }.get(val, "Unknown")
        except Exception:
            display, passed = "Unknown", False
        return {"key": "visual_fx", "value": display, "passed": passed}

    def _get_game_mode(self) -> dict:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\GameBar",
                0, winreg.KEY_READ,
            ) as k:
                val, _ = winreg.QueryValueEx(k, "AllowAutoGameMode")
            passed = (val == 1)
            display = "Enabled" if passed else "Disabled"
        except FileNotFoundError:
            # Key absent means Windows default — Game Mode is on by default
            display, passed = "Enabled (default)", True
        except Exception:
            display, passed = "Unknown", False
        return {"key": "game_mode", "value": display, "passed": passed}

    def _get_bg_processes(self) -> dict:
        try:
            running_names = {
                p.info["name"].lower()
                for p in psutil.process_iter(["name"])
                if p.info.get("name")
            }
            count = sum(1 for t in _BG_TARGETS if t in running_names)
            passed = count == 0
            display = f"{count} running" if count else "None"
        except Exception:
            count, display, passed = -1, "Unknown", False
        return {"key": "bg_processes", "value": display, "raw": count, "passed": passed}

    def _get_spatial_sound(self) -> dict:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\AudioSpatial",
                0, winreg.KEY_READ,
            ) as k:
                val, _ = winreg.QueryValueEx(k, "SpatialSoundType")
            passed = (val == 0)
            display = "Off" if passed else "Windows Sonic On"
        except FileNotFoundError:
            display, passed = "Off (default)", True
        except Exception:
            display, passed = "Unknown", False
        return {"key": "spatial_sound", "value": display, "passed": passed}

    def _get_cpu_boost(self) -> dict:
        try:
            result = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_PROCESSOR", "PERFBOOSTMODE"],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            ac_val = None
            for line in result.stdout.lower().split("\n"):
                if "current ac power setting index" in line and "0x" in line:
                    try:
                        ac_val = int(line.split("0x")[1].strip(), 16)
                    except (ValueError, IndexError):
                        pass
                    break
            if ac_val is None:
                display, passed = "Unknown", False
            elif ac_val == 0:
                display, passed = "Disabled", False
            elif ac_val == 1:
                display, passed = "Enabled", True
            elif ac_val == 2:
                display, passed = "Aggressive", True
            else:
                display, passed = f"Mode {ac_val}", True
        except Exception:
            display, passed = "Unknown", False
        return {"key": "cpu_boost", "value": display, "passed": passed}

    def _get_ram_free(self) -> dict:
        try:
            vm = psutil.virtual_memory()
            free_gb = vm.available / (1024 ** 3)
            passed = free_gb >= 4.0
            display = f"{free_gb:.1f} GB free"
        except Exception:
            free_gb, display, passed = 0.0, "Unknown", False
        return {"key": "ram_free", "value": display, "raw": free_gb, "passed": passed}

    def _get_startup_count(self) -> dict:
        count = 0
        for hive, path in [
            (winreg.HKEY_CURRENT_USER,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ]:
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
                    i = 0
                    while True:
                        try:
                            _, value, _ = winreg.EnumValue(k, i)
                            v_lower = value.lower()
                            if not any(p in v_lower for p in _PROTECTED_STARTUP):
                                count += 1
                            i += 1
                        except OSError:
                            break
            except Exception:
                pass
        passed = count < 5
        display = f"{count} entries"
        return {"key": "startup_count", "value": display, "raw": count, "passed": passed}

    # ── Public API ────────────────────────────────────────────────────────────

    def collect(self) -> dict:
        """
        Run all metric collectors.
        Returns dict keyed by metric key, each value is a fully-annotated dict.
        Network ping may take up to 2 s — call from a background thread.
        """
        collectors = [
            self._get_timer_res,
            self._get_core_parking,
            self._get_power_plan,
            self._get_mouse_accel,
            self._get_val_ping,
            self._get_visual_fx,
            self._get_game_mode,
            self._get_bg_processes,
            self._get_spatial_sound,
            self._get_cpu_boost,
            self._get_ram_free,
            self._get_startup_count,
        ]
        results = {}
        for fn in collectors:
            try:
                r = fn()
                k = r["key"]
                results[k] = {
                    **r,
                    "label":   _LABELS[k],
                    "icon":    _ICONS[k],
                    "optimal": _OPTIMAL_DESC[k],
                    "why":     _WHY[k],
                    "impact":  _IMPACT[k],
                    "weight":  _WEIGHTS[k],
                }
            except Exception:
                pass
        return results

    def compute_score(self, metrics: dict) -> int:
        """Return 0-100 competitive readiness score."""
        earned = sum(
            _WEIGHTS[k]
            for k, m in metrics.items()
            if m.get("passed") and k in _WEIGHTS
        )
        return min(100, max(0, earned))

    @staticmethod
    def score_grade(score: int) -> tuple:
        """Return (grade_str, hex_colour) for the given score."""
        if score >= 90:
            return "ELITE",          "#00d4aa"
        elif score >= 75:
            return "COMPETITIVE",    "#00d4aa"
        elif score >= 55:
            return "AVERAGE",        "#ffd700"
        elif score >= 35:
            return "NEEDS WORK",     "#ff9900"
        else:
            return "UNOPTIMISED",    "#ff4655"

    # ── Snapshot persistence ──────────────────────────────────────────────────

    def save_snapshot(self, metrics: dict, score: int) -> None:
        """Persist a before-snapshot to disk for later comparison."""
        snap = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "score": score,
            "metrics": {
                k: {"value": m["value"], "passed": m["passed"]}
                for k, m in metrics.items()
            },
        }
        try:
            with open(_SNAP_FILE, "w") as f:
                json.dump(snap, f, indent=2)
        except Exception:
            pass

    def load_snapshot(self) -> dict | None:
        """Load the saved before-snapshot, or None if not present."""
        try:
            with open(_SNAP_FILE) as f:
                return json.load(f)
        except Exception:
            return None

    def delete_snapshot(self) -> None:
        try:
            os.remove(_SNAP_FILE)
        except Exception:
            pass
