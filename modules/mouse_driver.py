# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
mouse_driver.py — Advanced mouse driver tools for Valo Optimise
Provides: PollingRateMonitor, PointerBallistics, SensitivityProfileManager,
          MouseDeviceInfo, RawInputChecker
"""

import ctypes
import ctypes.wintypes as wt
import threading
import time
import json
import os
import subprocess
import winreg

# ── Constants ─────────────────────────────────────────────────────────────────

WH_MOUSE_LL = 14
HC_ACTION   = 0

SPI_SETMOUSE      = 0x0004
SPI_SETMOUSESPEED = 0x0071
SPIF_SENDCHANGE   = 0x0002

# 1:1 linear ballistics values (no hidden acceleration at any speed)
LINEAR_X = bytes.fromhex(
    "0000000000000000"
    "0000380000000000"
    "0000700000000000"
    "0000A80000000000"
    "0000D80000000000"
)
LINEAR_Y = bytes.fromhex(
    "0000000000000000"
    "0000380000000000"
    "0000700000000000"
    "0000A80000000000"
    "0000D80000000000"
)

_PROFILES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "sensitivity_profiles.json"
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. PollingRateMonitor
# ══════════════════════════════════════════════════════════════════════════════

class PollingRateMonitor:
    """Measures raw mouse polling rate using a Windows low-level mouse hook."""

    def measure(self, seconds: int = 2) -> int:
        """Returns measured polling rate in Hz. User must move mouse during measurement."""
        count_holder = [0]
        done         = threading.Event()
        hook_holder  = [None]

        HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)

        def proc(nCode, wParam, lParam):
            if nCode >= HC_ACTION:
                count_holder[0] += 1
            return ctypes.windll.user32.CallNextHookEx(hook_holder[0], nCode, wParam, lParam)

        cb = HOOKPROC(proc)

        def run():
            hook_holder[0] = ctypes.windll.user32.SetWindowsHookExW(
                WH_MOUSE_LL, cb, None, 0
            )
            msg      = wt.MSG()
            deadline = time.perf_counter() + seconds
            while time.perf_counter() < deadline:
                while ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 1
                ):
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.0005)
            ctypes.windll.user32.UnhookWindowsHookEx(hook_holder[0])
            done.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()
        done.wait(timeout=seconds + 2)

        elapsed = seconds
        rate    = count_holder[0] / elapsed
        # Round to nearest standard polling rate
        for standard in [125, 250, 500, 1000, 2000, 4000, 8000]:
            if rate < standard * 1.25:
                return standard
        return int(rate)


# ══════════════════════════════════════════════════════════════════════════════
# 2. PointerBallistics
# ══════════════════════════════════════════════════════════════════════════════

class PointerBallistics:
    """Read/write SmoothMouseXCurve and SmoothMouseYCurve for 1:1 linear movement."""

    _KEY      = r"Control Panel\Mouse"
    _backup_x = None
    _backup_y = None

    def get_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0, winreg.KEY_READ
            ) as k:
                x, _ = winreg.QueryValueEx(k, "SmoothMouseXCurve")
                y, _ = winreg.QueryValueEx(k, "SmoothMouseYCurve")
                if x == LINEAR_X and y == LINEAR_Y:
                    return "Linear 1:1 (optimized)"
                return "Windows default"
        except Exception:
            return "Unknown"

    def set_linear(self) -> tuple:
        """Set pointer ballistics to perfect 1:1 linear. Returns (ok, msg)."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as k:
                # Backup existing values
                try:
                    self._backup_x, _ = winreg.QueryValueEx(k, "SmoothMouseXCurve")
                    self._backup_y, _ = winreg.QueryValueEx(k, "SmoothMouseYCurve")
                except FileNotFoundError:
                    self._backup_x = None
                    self._backup_y = None

                winreg.SetValueEx(k, "SmoothMouseXCurve", 0, winreg.REG_BINARY, LINEAR_X)
                winreg.SetValueEx(k, "SmoothMouseYCurve", 0, winreg.REG_BINARY, LINEAR_Y)
            return True, "Pointer ballistics set to perfect 1:1 linear — no hidden acceleration at any speed."
        except PermissionError:
            return False, "Permission denied. Run as Administrator."
        except Exception as e:
            return False, f"Failed to set ballistics: {e}"

    def restore_default(self) -> tuple:
        """Restore pointer ballistics to backed-up or Windows default. Returns (ok, msg)."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as k:
                if self._backup_x is not None and self._backup_y is not None:
                    winreg.SetValueEx(k, "SmoothMouseXCurve", 0, winreg.REG_BINARY, self._backup_x)
                    winreg.SetValueEx(k, "SmoothMouseYCurve", 0, winreg.REG_BINARY, self._backup_y)
                    return True, "Pointer ballistics restored to previous backup."
                else:
                    # Delete the values so Windows uses its built-in defaults
                    try:
                        winreg.DeleteValue(k, "SmoothMouseXCurve")
                    except FileNotFoundError:
                        pass
                    try:
                        winreg.DeleteValue(k, "SmoothMouseYCurve")
                    except FileNotFoundError:
                        pass
                    return True, "Pointer ballistics restored to Windows default."
        except PermissionError:
            return False, "Permission denied. Run as Administrator."
        except Exception as e:
            return False, f"Failed to restore ballistics: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. SensitivityProfileManager
# ══════════════════════════════════════════════════════════════════════════════

class SensitivityProfileManager:
    """Manage named sensitivity profiles stored in sensitivity_profiles.json."""

    _MOUSE_KEY = r"Control Panel\Mouse"

    def _load(self) -> list:
        try:
            if os.path.exists(_PROFILES_PATH):
                with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save_file(self, profiles: list):
        try:
            with open(_PROFILES_PATH, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
        except Exception:
            pass

    def list_profiles(self) -> list:
        """Return list of profile dicts."""
        return self._load()

    def save_profile(self, name: str, dpi: int, sens: float, ptr_speed: int) -> tuple:
        """Save or overwrite a named sensitivity profile. Returns (ok, msg)."""
        try:
            profiles = self._load()
            # Remove existing with same name
            profiles = [p for p in profiles if p.get("name") != name]
            profiles.append({
                "name":          name,
                "dpi":           int(dpi),
                "sensitivity":   float(sens),
                "pointer_speed": int(ptr_speed),
            })
            self._save_file(profiles)
            return True, f"Profile '{name}' saved."
        except Exception as e:
            return False, f"Failed to save profile: {e}"

    def delete_profile(self, name: str) -> tuple:
        """Delete a named profile. Returns (ok, msg)."""
        try:
            profiles = self._load()
            new_profiles = [p for p in profiles if p.get("name") != name]
            if len(new_profiles) == len(profiles):
                return False, f"Profile '{name}' not found."
            self._save_file(new_profiles)
            return True, f"Profile '{name}' deleted."
        except Exception as e:
            return False, f"Failed to delete profile: {e}"

    def apply_profile(self, name: str) -> tuple:
        """Apply a profile: sets registry sensitivity and pointer speed. Returns (ok, msg)."""
        profiles = self._load()
        profile  = next((p for p in profiles if p.get("name") == name), None)
        if not profile:
            return False, f"Profile '{name}' not found."

        ptr_speed = int(profile.get("pointer_speed", 6))
        sens_str  = str(profile.get("sensitivity", 0.4))

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._MOUSE_KEY, 0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as k:
                winreg.SetValueEx(k, "MouseSensitivity", 0, winreg.REG_SZ, sens_str)
                winreg.SetValueEx(k, "MouseSpeed",       0, winreg.REG_SZ, "0")
                winreg.SetValueEx(k, "MouseThreshold1",  0, winreg.REG_SZ, "0")
                winreg.SetValueEx(k, "MouseThreshold2",  0, winreg.REG_SZ, "0")
        except Exception as e:
            return False, f"Registry write failed: {e}"

        # Apply pointer speed via SystemParametersInfo
        try:
            ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETMOUSESPEED, 0, ptr_speed, SPIF_SENDCHANGE
            )
        except Exception as e:
            return False, f"SPI_SETMOUSESPEED failed: {e}"

        return (
            True,
            f"Profile '{name}' applied — DPI: {profile.get('dpi')}, "
            f"Sens: {profile.get('sensitivity')}, Pointer Speed: {ptr_speed}."
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. MouseDeviceInfo
# ══════════════════════════════════════════════════════════════════════════════

class MouseDeviceInfo:
    """Query connected mouse devices via WMI/PowerShell."""

    def get_devices(self) -> list:
        """Return list of dicts: {name, vid, pid, instance_id}."""
        try:
            ps_cmd = (
                "Get-PnpDevice -Class Mouse -Status OK "
                "| Select-Object FriendlyName,InstanceId "
                "| ConvertTo-Json"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            raw = result.stdout.strip()
            if not raw:
                return []

            data = json.loads(raw)
            # PowerShell returns a single object (not list) when only one result
            if isinstance(data, dict):
                data = [data]

            devices = []
            for item in data:
                name        = item.get("FriendlyName") or "Unknown Mouse"
                instance_id = item.get("InstanceId")  or ""
                vid, pid    = self._extract_vid_pid(instance_id)
                devices.append({
                    "name":        name,
                    "vid":         vid,
                    "pid":         pid,
                    "instance_id": instance_id,
                })
            return devices
        except Exception:
            return []

    @staticmethod
    def _extract_vid_pid(instance_id: str) -> tuple:
        """Extract VID and PID from a device InstanceId string."""
        vid = ""
        pid = ""
        try:
            upper = instance_id.upper()
            if "VID_" in upper:
                vid_start = upper.index("VID_") + 4
                vid = upper[vid_start:vid_start + 4]
            if "PID_" in upper:
                pid_start = upper.index("PID_") + 4
                pid = upper[pid_start:pid_start + 4]
        except Exception:
            pass
        return vid, pid


# ══════════════════════════════════════════════════════════════════════════════
# 5. RawInputChecker
# ══════════════════════════════════════════════════════════════════════════════

class RawInputChecker:
    """Check if Windows raw input is configured correctly for competitive play."""

    _KEY = r"Control Panel\Mouse"

    def check(self) -> dict:
        """
        Returns dict:
          {
            "epp_off":          bool,
            "thresholds_zero":  bool,
            "overall":          str   # "Fully Optimized" | "Partial" | "Not Configured"
          }
        """
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0, winreg.KEY_READ
            ) as k:
                def _qv(name):
                    try:
                        v, _ = winreg.QueryValueEx(k, name)
                        return str(v)
                    except Exception:
                        return None

                mouse_speed = _qv("MouseSpeed")
                threshold1  = _qv("MouseThreshold1")
                threshold2  = _qv("MouseThreshold2")

                epp_off         = (mouse_speed == "0")
                thresholds_zero = (threshold1 == "0" and threshold2 == "0")

        except Exception:
            epp_off         = False
            thresholds_zero = False

        both = epp_off and thresholds_zero
        neither = not epp_off and not thresholds_zero

        if both:
            overall = "Fully Optimized"
        elif neither:
            overall = "Not Configured"
        else:
            overall = "Partial"

        return {
            "epp_off":         epp_off,
            "thresholds_zero": thresholds_zero,
            "overall":         overall,
        }
