# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import ctypes
import subprocess
import winreg

# Windows API constants
SPI_SETMOUSE   = 0x0004
SPI_GETMOUSE   = 0x0003
SPIF_SENDCHANGE = 0x0002


class MouseOptimizer:

    _MOUSE_KEY = r"Control Panel\Mouse"

    def _read_mouse_value(self, name: str) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._MOUSE_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, name)
                return str(val)
        except Exception:
            return ""

    def _write_mouse_value(self, name: str, value: str) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._MOUSE_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            return True
        except Exception:
            return False

    def get_acceleration_status(self) -> str:
        speed = self._read_mouse_value("MouseSpeed")
        if speed == "0":
            return "Disabled"
        if speed in ("1", "2"):
            return "Enabled"
        return "Unknown"

    def disable_acceleration(self) -> tuple:
        """
        Disables Windows mouse acceleration (Enhance Pointer Precision).
        Sets MouseSpeed=0, MouseThreshold1=0, MouseThreshold2=0 and applies immediately.
        """
        ok1 = self._write_mouse_value("MouseSpeed", "0")
        ok2 = self._write_mouse_value("MouseThreshold1", "0")
        ok3 = self._write_mouse_value("MouseThreshold2", "0")

        if not (ok1 and ok2 and ok3):
            return False, "Failed to write registry values. Run as Administrator."

        # Apply immediately via Win32 API — no reboot needed
        params = (ctypes.c_int * 3)(0, 0, 0)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETMOUSE, 0, params, SPIF_SENDCHANGE
        )
        return True, "Mouse acceleration disabled. Effective immediately — no reboot needed."

    def enable_acceleration(self) -> tuple:
        """Restores Windows default mouse acceleration values."""
        ok1 = self._write_mouse_value("MouseSpeed", "1")
        ok2 = self._write_mouse_value("MouseThreshold1", "6")
        ok3 = self._write_mouse_value("MouseThreshold2", "10")

        if not (ok1 and ok2 and ok3):
            return False, "Failed to restore registry values."

        params = (ctypes.c_int * 3)(6, 10, 1)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETMOUSE, 0, params, SPIF_SENDCHANGE
        )
        return True, "Mouse acceleration restored to Windows defaults."

    def get_pointer_speed(self) -> int:
        """Returns Windows pointer speed (1–20). Default is 10."""
        try:
            val = self._read_mouse_value("MouseSensitivity")
            return int(val) if val else 10
        except Exception:
            return 10

    def get_full_status(self) -> dict:
        return {
            "acceleration": self.get_acceleration_status(),
            "pointer_speed": self.get_pointer_speed(),
            "threshold1": self._read_mouse_value("MouseThreshold1"),
            "threshold2": self._read_mouse_value("MouseThreshold2"),
        }

    # ── USB Selective Suspend ─────────────────────────────────────────────────

    _USB_SUBGROUP = "2a737441-1930-4402-8d77-b2bebba308a3"
    _USB_SS_SETTING = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"

    def get_usb_selective_suspend_status(self) -> str:
        try:
            r = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT",
                 self._USB_SUBGROUP, self._USB_SS_SETTING],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.splitlines():
                if "Current AC Power Setting Index:" in line:
                    val = int(line.split(":")[-1].strip(), 16)
                    return "Disabled (optimized)" if val == 0 else "Enabled (default)"
            return "Unknown"
        except Exception:
            return "Unknown"

    def disable_usb_selective_suspend(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT",
             self._USB_SUBGROUP, self._USB_SS_SETTING, "0"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT",
             self._USB_SUBGROUP, self._USB_SS_SETTING, "0"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "USB Selective Suspend disabled — mouse/keyboard never micro-pause from USB power-gating."

    def enable_usb_selective_suspend(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT",
             self._USB_SUBGROUP, self._USB_SS_SETTING, "1"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT",
             self._USB_SUBGROUP, self._USB_SS_SETTING, "1"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "USB Selective Suspend restored to default."

    # ── USB Root Hub Power Management ─────────────────────────────────────────

    def _get_usb_hub_device_param_paths(self) -> list:
        paths = []
        base = r"SYSTEM\CurrentControlSet\Enum\USB"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as bk:
                i = 0
                while True:
                    try:
                        vid_key = winreg.EnumKey(bk, i)
                        i += 1
                        if "ROOT_HUB" not in vid_key.upper():
                            continue
                        vid_path = f"{base}\\{vid_key}"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, vid_path) as vk:
                            j = 0
                            while True:
                                try:
                                    inst = winreg.EnumKey(vk, j)
                                    j += 1
                                    paths.append(f"{vid_path}\\{inst}\\Device Parameters")
                                except OSError:
                                    break
                    except OSError:
                        break
        except Exception:
            pass
        return paths

    def get_usb_hub_power_status(self) -> str:
        paths = self._get_usb_hub_device_param_paths()
        if not paths:
            return "Unknown"
        for path in paths:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ
                ) as k:
                    val, _ = winreg.QueryValueEx(k, "EnhancedPowerManagementEnabled")
                    if val == 0:
                        return "Disabled (optimized)"
            except Exception:
                pass
        return "Enabled (default)"

    def disable_usb_hub_power(self) -> tuple:
        paths = self._get_usb_hub_device_param_paths()
        if not paths:
            return False, "No USB root hubs found in registry."
        count = 0
        for path in paths:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, path, 0,
                    winreg.KEY_SET_VALUE | winreg.KEY_READ
                ) as k:
                    winreg.SetValueEx(k, "EnhancedPowerManagementEnabled", 0, winreg.REG_DWORD, 0)
                    count += 1
            except Exception:
                pass
        if count:
            return True, f"USB root hub power management disabled on {count} hub(s) — mouse input never delayed by USB controller sleeping."
        return False, "Could not write USB hub keys. Run as Administrator."

    def enable_usb_hub_power(self) -> tuple:
        paths = self._get_usb_hub_device_param_paths()
        count = 0
        for path in paths:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, path, 0,
                    winreg.KEY_SET_VALUE | winreg.KEY_READ
                ) as k:
                    winreg.SetValueEx(k, "EnhancedPowerManagementEnabled", 0, winreg.REG_DWORD, 1)
                    count += 1
            except Exception:
                pass
        return True, f"USB root hub power management restored on {count} hub(s)."

    # ── eDPI Calculator ───────────────────────────────────────────────────────

    @staticmethod
    def calculate_edpi(dpi: float, sensitivity: float) -> float:
        """eDPI = mouse DPI × Valorant in-game sensitivity."""
        return round(dpi * sensitivity, 1)

    @staticmethod
    def edpi_recommendation(edpi: float) -> str:
        if edpi < 200:
            return "Very low — good for large arm movements, common in pro play."
        if edpi < 400:
            return "Low — standard pro range. Maximum precision for long-range."
        if edpi < 800:
            return "Medium — balanced. Good starting point for most players."
        if edpi < 1200:
            return "High — better for close-range / flick shots."
        return "Very high — hard to control for precise aim. Consider lowering."

    # ── Aim Trainer Launch ────────────────────────────────────────────────────

    def launch_aim_trainer(self, app: str) -> tuple:
        """Launch KovaaK's or AimLab via Steam protocol."""
        app_ids = {
            "KovaaK's":  "824270",
            "AimLab":    "714010",
        }
        app_id = app_ids.get(app)
        if not app_id:
            return False, f"Unknown aim trainer: {app}"
        try:
            import subprocess as _sp
            _sp.Popen(["cmd", "/c", "start", "", f"steam://rungameid/{app_id}"])
            return True, f"Launching {app} via Steam..."
        except Exception as e:
            return False, str(e)
