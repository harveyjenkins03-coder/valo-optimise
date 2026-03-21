import subprocess
import winreg

_DISPLAY_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
_HAGS_KEY = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"


class GpuOptimizer:

    def _find_amd_adapter_key(self) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _DISPLAY_CLASS_KEY) as base:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(base, i)
                        i += 1
                        if not sub.isdigit():
                            continue
                        sub_path = f"{_DISPLAY_CLASS_KEY}\\{sub}"
                        try:
                            with winreg.OpenKey(
                                winreg.HKEY_LOCAL_MACHINE, sub_path, 0, winreg.KEY_READ
                            ) as k:
                                winreg.QueryValueEx(k, "ColourFullscreenBrightness_DEF")
                                return sub_path
                        except FileNotFoundError:
                            pass
                        except Exception:
                            pass
                    except OSError:
                        break
        except Exception:
            pass
        return None

    def is_amd_available(self) -> bool:
        return self._find_amd_adapter_key() is not None

    # ── ULPS (Ultra Low Power State) ──────────────────────────────────────────

    def get_ulps_status(self) -> str:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return "Unknown"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "EnableULPS")
                return "Disabled (optimized)" if val == 0 else "Enabled (default)"
        except FileNotFoundError:
            return "Enabled (default)"
        except Exception:
            return "Unknown"

    def disable_ulps(self) -> tuple:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return False, "AMD adapter registry key not found."
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "EnableULPS", 0, winreg.REG_DWORD, 0)
            return True, "AMD ULPS disabled — GPU stays at full power, eliminating frame-time spikes when the driver wakes from low-power state."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def enable_ulps(self) -> tuple:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return False, "AMD adapter registry key not found."
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "EnableULPS", 0, winreg.REG_DWORD, 1)
            return True, "AMD ULPS restored to default."
        except Exception as e:
            return False, str(e)

    # ── AMD Chill ─────────────────────────────────────────────────────────────

    def get_chill_status(self) -> str:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return "Unknown"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "KMD_EnableChill")
                return "Disabled (optimized)" if val == 0 else "Enabled"
        except FileNotFoundError:
            return "Disabled (default)"
        except Exception:
            return "Unknown"

    def disable_chill(self) -> tuple:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return False, "AMD adapter registry key not found."
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "KMD_EnableChill", 0, winreg.REG_DWORD, 0)
            return True, "AMD Chill disabled — FPS will no longer be capped by AMD's power-saver feature."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def enable_chill(self) -> tuple:
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return False, "AMD adapter registry key not found."
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "KMD_EnableChill", 0, winreg.REG_DWORD, 1)
            return True, "AMD Chill restored to default."
        except Exception as e:
            return False, str(e)

    # ── HAGS (Hardware-Accelerated GPU Scheduling) ────────────────────────────

    def get_hags_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _HAGS_KEY, 0, winreg.KEY_READ
            ) as k:
                val, _ = winreg.QueryValueEx(k, "HwSchMode")
                return "Enabled (optimized)" if val == 2 else "Disabled"
        except FileNotFoundError:
            return "Disabled (default)"
        except Exception:
            return "Unknown"

    def enable_hags(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _HAGS_KEY, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "HwSchMode", 0, winreg.REG_DWORD, 2)
            return True, "Hardware-Accelerated GPU Scheduling enabled — GPU manages its own work queue, reducing CPU overhead. Reboot required."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def disable_hags(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _HAGS_KEY, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "HwSchMode", 0, winreg.REG_DWORD, 1)
            return True, "HAGS disabled. Reboot required to take effect."
        except Exception as e:
            return False, str(e)
