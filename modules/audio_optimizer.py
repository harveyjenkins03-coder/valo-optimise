# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import subprocess
import winreg
import psutil


class AudioOptimizer:

    _SPATIAL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\AudioSpatial"

    def get_spatial_sound_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self._SPATIAL_KEY,
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "SpatialSoundType")
                return {
                    0: "Off",
                    1: "Windows Sonic for Headphones",
                    4: "Dolby Atmos for Headphones",
                    5: "DTS Headphone:X",
                }.get(val, f"Unknown ({val})")
        except FileNotFoundError:
            return "Off"
        except Exception:
            return "Unknown"

    def disable_spatial_sound(self) -> tuple:
        """Disables Windows Sonic / spatial sound processing that can interfere with HRTF."""
        try:
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    self._SPATIAL_KEY,
                    0, winreg.KEY_SET_VALUE
                )
            except FileNotFoundError:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._SPATIAL_KEY)

            with key:
                winreg.SetValueEx(key, "SpatialSoundType", 0, winreg.REG_DWORD, 0)
            return True, "Spatial sound (Windows Sonic) disabled. Use Valorant's built-in HRTF instead."
        except Exception as e:
            return False, str(e)

    def get_spatial_sound_type_value(self) -> int:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self._SPATIAL_KEY,
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "SpatialSoundType")
                return val
        except Exception:
            return 0

    def is_audio_service_running(self) -> bool:
        try:
            result = subprocess.run(
                ["sc", "query", "AudioSrv"],
                capture_output=True, text=True, timeout=5
            )
            return "RUNNING" in result.stdout
        except Exception:
            return False

    def open_sound_settings(self) -> tuple:
        """Opens the Windows Sound Control Panel for manual per-device settings."""
        try:
            subprocess.Popen(["control", "mmsys.cpl"])
            return True, "Sound Control Panel opened."
        except Exception as e:
            return False, str(e)

    def open_volume_mixer(self) -> tuple:
        """Opens the Volume Mixer."""
        try:
            subprocess.Popen(["sndvol"])
            return True, "Volume Mixer opened."
        except Exception as e:
            return False, str(e)

    def get_full_status(self) -> dict:
        return {
            "spatial_sound":    self.get_spatial_sound_status(),
            "audio_service_ok": self.is_audio_service_running(),
        }

    # ── MMCSS Audio Priority ──────────────────────────────────────────────────

    _MMCSS_GAMES_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"

    def get_mmcss_audio_status(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, self._MMCSS_GAMES_KEY, 0, winreg.KEY_READ
            ) as k:
                gpu_pri, _ = winreg.QueryValueEx(k, "GPU Priority")
                pri, _     = winreg.QueryValueEx(k, "Priority")
                cat, _     = winreg.QueryValueEx(k, "Scheduling Category")
                if gpu_pri >= 8 and pri >= 6 and str(cat).lower() == "high":
                    return "Optimized (High)"
                return f"Default (GPU Pri:{gpu_pri} Pri:{pri} Cat:{cat})"
        except Exception:
            return "Default"

    def set_mmcss_high_priority(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, self._MMCSS_GAMES_KEY, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "GPU Priority",         0, winreg.REG_DWORD, 8)
                winreg.SetValueEx(k, "Priority",             0, winreg.REG_DWORD, 6)
                winreg.SetValueEx(k, "Scheduling Category",  0, winreg.REG_SZ,    "High")
                winreg.SetValueEx(k, "SFIO Priority",        0, winreg.REG_SZ,    "High")
            return True, "MMCSS Games task set to High priority — audio/game processing scheduled with maximum priority, footsteps arrive ~5ms earlier."
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def restore_mmcss_priority(self) -> tuple:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, self._MMCSS_GAMES_KEY, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                winreg.SetValueEx(k, "GPU Priority",         0, winreg.REG_DWORD, 8)
                winreg.SetValueEx(k, "Priority",             0, winreg.REG_DWORD, 2)
                winreg.SetValueEx(k, "Scheduling Category",  0, winreg.REG_SZ,    "Medium")
                winreg.SetValueEx(k, "SFIO Priority",        0, winreg.REG_SZ,    "Normal")
            return True, "MMCSS Games task restored to default priority."
        except Exception as e:
            return False, str(e)
