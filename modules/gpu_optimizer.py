import subprocess
import winreg
import os
import shutil

_DISPLAY_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
_HAGS_KEY          = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"

# NVIDIA registry paths
_NV_DISPLAY_KEY    = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
_NV_DRV_FEATURES   = r"SOFTWARE\NVIDIA Corporation\Global\NVTweak"
_NV_PERF_LEVEL_KEY = r"SYSTEM\CurrentControlSet\Services\nvlddmkm\Global\NVTweak"

# Shader cache locations
_SHADER_CACHE_PATHS = [
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "NVIDIA", "DXCache"),
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "NVIDIA", "GLCache"),
    os.path.join(os.path.expanduser("~"), "AppData", "LocalLow", "NVIDIA", "PerDriverVersion"),
    os.path.join(os.path.expanduser("~"), "AppData", "Local", "D3DSCache"),
]


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

    # ── NVIDIA detection ──────────────────────────────────────────────────────

    def is_nvidia_available(self) -> bool:
        """Return True if an NVIDIA GPU is detected."""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name"],
                capture_output=True, text=True, timeout=8
            )
            return "nvidia" in result.stdout.lower()
        except Exception:
            return False

    def get_nvidia_driver_version(self) -> str:
        """Return the installed NVIDIA driver version string."""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "where",
                 "Name like '%NVIDIA%'", "get", "DriverVersion"],
                capture_output=True, text=True, timeout=8
            )
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and "DriverVersion" not in l]
            return lines[0] if lines else "Unknown"
        except Exception:
            return "Unknown"

    # ── NVIDIA Reflex (Low Latency Mode) ──────────────────────────────────────

    def get_reflex_status(self) -> str:
        """
        NVIDIA Reflex is controlled per-game inside the game itself.
        This method checks whether the driver-level low-latency hint is set.
        """
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\NVIDIA Corporation\Global\NVTweak",
                0, winreg.KEY_READ
            ) as k:
                val, _ = winreg.QueryValueEx(k, "LowLatency")
                return "Enabled" if val == 1 else "Disabled (default)"
        except FileNotFoundError:
            return "Disabled (default)"
        except Exception:
            return "Unknown"

    def enable_reflex_low_latency(self) -> tuple:
        """Enable NVIDIA driver-level low-latency mode (equivalent to NVIDIA Control Panel Ultra Low Latency)."""
        try:
            key_path = r"SOFTWARE\NVIDIA Corporation\Global\NVTweak"
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "LowLatency", 0, winreg.REG_DWORD, 1)
            return True, "NVIDIA Low Latency mode enabled — reduces render queue depth for lower input lag."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def disable_reflex_low_latency(self) -> tuple:
        """Restore NVIDIA low-latency mode to driver default."""
        try:
            key_path = r"SOFTWARE\NVIDIA Corporation\Global\NVTweak"
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "LowLatency", 0, winreg.REG_DWORD, 0)
            return True, "NVIDIA Low Latency mode restored to default."
        except Exception as e:
            return False, str(e)

    # ── NVIDIA Power Management ───────────────────────────────────────────────

    def get_nvidia_power_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\NVIDIA Corporation\Global\NVTweak",
                0, winreg.KEY_READ
            ) as k:
                val, _ = winreg.QueryValueEx(k, "PowerMizerEnable")
                return "Max Performance" if val == 1 else "Adaptive (default)"
        except FileNotFoundError:
            return "Adaptive (default)"
        except Exception:
            return "Unknown"

    def set_nvidia_max_performance(self) -> tuple:
        """Force NVIDIA GPU to maximum performance power state — prevents clock throttling mid-match."""
        try:
            key_path = r"SOFTWARE\NVIDIA Corporation\Global\NVTweak"
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "PowerMizerEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "PowerMizerLevel",  0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "PowerMizerLevelAC", 0, winreg.REG_DWORD, 1)
            return True, "NVIDIA GPU locked to Maximum Performance — eliminates mid-game clock speed drops."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def restore_nvidia_adaptive_power(self) -> tuple:
        """Restore NVIDIA adaptive power management."""
        try:
            key_path = r"SOFTWARE\NVIDIA Corporation\Global\NVTweak"
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "PowerMizerEnable",  0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(k, "PowerMizerLevel",   0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(k, "PowerMizerLevelAC", 0, winreg.REG_DWORD, 0)
            return True, "NVIDIA power management restored to Adaptive."
        except Exception as e:
            return False, str(e)

    # ── Shader cache clear ────────────────────────────────────────────────────

    def get_shader_cache_size(self) -> str:
        """Return total size of NVIDIA/D3D shader caches."""
        total = 0
        for path in _SHADER_CACHE_PATHS:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        try:
                            total += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
        if total == 0:
            return "0 MB"
        mb = total / (1024 * 1024)
        return f"{mb:.1f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"

    def clear_shader_cache(self) -> tuple:
        """
        Delete NVIDIA DX/GL shader caches and the Windows D3DSCache.
        Windows rebuilds them on next launch — clears corrupted/bloated cache entries.
        Safe to run; does not touch game files.
        """
        cleared, failed = 0, []
        for cache_path in _SHADER_CACHE_PATHS:
            if not os.path.isdir(cache_path):
                continue
            for item in os.listdir(cache_path):
                full = os.path.join(cache_path, item)
                try:
                    if os.path.isfile(full):
                        os.remove(full)
                    elif os.path.isdir(full):
                        shutil.rmtree(full)
                    cleared += 1
                except Exception as e:
                    failed.append(f"{item}: {e}")
        if cleared == 0 and not failed:
            return True, "Shader cache already empty."
        msg = f"Cleared {cleared} shader cache item(s). Windows will rebuild on next launch."
        if failed:
            msg += f" ({len(failed)} item(s) could not be removed — may be in use.)"
        return True, msg
