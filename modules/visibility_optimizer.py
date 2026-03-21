import winreg

# AMD display adapter class GUID
_DISPLAY_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"

# Fullscreen color presets.
# Brightness: integer "R G B", neutral = "0 0 0", positive = brighter.
# Contrast:   float   "R G B", neutral = "1.0 1.0 1.0".
# Gamma:      float   "R G B", neutral = "1.0 1.0 1.0", >1 = brighter mids.
PRESETS = {
    "Default": {
        "brightness": "0 0 0",
        "contrast":   "1.0 1.0 1.0",
        "gamma":      "1.0 1.0 1.0",
    },
    "Subtle": {
        "brightness": "5 5 5",
        "contrast":   "1.05 1.05 1.05",
        "gamma":      "1.0 1.0 1.0",
    },
    "Competitive": {
        "brightness": "10 10 10",
        "contrast":   "1.10 1.10 1.10",
        "gamma":      "1.0 1.0 1.0",
    },
    "Max Visibility": {
        "brightness": "20 20 20",
        "contrast":   "1.20 1.20 1.20",
        "gamma":      "1.05 1.05 1.05",
    },
}

PRESET_NOTES = {
    "Default":        "Factory defaults — no adjustment.",
    "Subtle":         "+5 brightness, +5% contrast. Barely noticeable but cleaner darks.",
    "Competitive":    "+10 brightness, +10% contrast. Dark areas lift noticeably. Recommended.",
    "Max Visibility": "+20 brightness, +20% contrast, slight gamma lift. Maximum enemy clarity.",
}


class VisibilityOptimizer:

    def _find_amd_adapter_key(self) -> str | None:
        """
        Enumerates display adapter subkeys to find the AMD one.
        Returns the registry path string, or None if not found.
        """
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
        """Returns True if AMD display adapter registry keys are present."""
        return self._find_amd_adapter_key() is not None

    def get_current_values(self) -> dict:
        """Returns {brightness, contrast, gamma} strings for current fullscreen settings."""
        key_path = self._find_amd_adapter_key()
        if not key_path:
            return {}
        result = {}
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ
            ) as k:
                for reg_name, field in [
                    ("ColourFullscreenBrightness_DEF", "brightness"),
                    ("ColourFullscreenContrast_DEF",   "contrast"),
                    ("ColourFullscreenGamma_DEF",       "gamma"),
                ]:
                    try:
                        val, _ = winreg.QueryValueEx(k, reg_name)
                        result[field] = str(val)
                    except FileNotFoundError:
                        result[field] = "Unknown"
        except Exception:
            pass
        return result

    def get_active_preset(self) -> str:
        """Returns the preset name matching current values, or 'Custom' / 'Unknown'."""
        current = self.get_current_values()
        if not current:
            return "Unknown"
        for name, preset in PRESETS.items():
            if (current.get("brightness") == preset["brightness"] and
                    current.get("contrast")   == preset["contrast"] and
                    current.get("gamma")      == preset["gamma"]):
                return name
        return "Custom"

    def apply_preset(self, preset_name: str) -> tuple:
        """
        Writes the preset values to AMD fullscreen AND desktop color keys.
        Changes are read by the AMD driver when Valorant enters exclusive fullscreen.
        No reboot is required.
        """
        preset = PRESETS.get(preset_name)
        if not preset:
            return False, f"Unknown preset: {preset_name}"

        key_path = self._find_amd_adapter_key()
        if not key_path:
            return False, "AMD display adapter registry keys not found. Is an AMD GPU installed?"

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as k:
                pairs = [
                    ("ColourFullscreenBrightness_DEF", "ColourDesktopBrightness_DEF", "brightness"),
                    ("ColourFullscreenContrast_DEF",   "ColourDesktopContrast_DEF",   "contrast"),
                    ("ColourFullscreenGamma_DEF",       "ColourDesktopGamma_DEF",       "gamma"),
                ]
                for fs_name, dt_name, field in pairs:
                    val = preset[field]
                    winreg.SetValueEx(k, fs_name, 0, winreg.REG_SZ, val)
                    winreg.SetValueEx(k, dt_name, 0, winreg.REG_SZ, val)

            return True, (
                f"'{preset_name}' preset applied — "
                f"brightness={preset['brightness']}, contrast={preset['contrast']}, "
                f"gamma={preset['gamma']}. "
                "Values load when Valorant enters exclusive fullscreen."
            )
        except PermissionError:
            return False, "Permission denied — run the app as Administrator."
        except Exception as e:
            return False, str(e)
