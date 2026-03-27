import os
import shutil
import datetime
import configparser
import winreg


# Competitive settings to apply — all quality settings to minimum,
# VSync off, uncapped FPS, exclusive fullscreen.
COMPETITIVE_SETTINGS = {
    "sg.ShadowQuality":       "0",
    "sg.PostProcessQuality":  "0",
    "sg.TextureQuality":      "0",
    "sg.EffectsQuality":      "0",
    "sg.FoliageQuality":      "0",
    "sg.ViewDistanceQuality": "0",
    "bUseVSync":              "False",
    "FrameRateLimit":         "0.000000",
    "FullscreenMode":         "0",
}

SETTING_LABELS = {
    "sg.ShadowQuality":       "Shadow Quality",
    "sg.PostProcessQuality":  "Post-Process Quality",
    "sg.TextureQuality":      "Texture Quality",
    "sg.EffectsQuality":      "Effects Quality",
    "sg.FoliageQuality":      "Foliage Quality",
    "sg.ViewDistanceQuality": "View Distance Quality",
    "bUseVSync":              "VSync",
    "FrameRateLimit":         "FPS Limit",
    "FullscreenMode":         "Fullscreen Mode",
}

SETTING_NOTES = {
    "sg.ShadowQuality":       "0 = Off (best FPS + visibility)",
    "sg.PostProcessQuality":  "0 = Off (no blur effects)",
    "sg.TextureQuality":      "0 = Low (no visual impact on gameplay)",
    "sg.EffectsQuality":      "0 = Low (cleaner ability visuals)",
    "sg.FoliageQuality":      "0 = Low (no gameplay impact)",
    "sg.ViewDistanceQuality": "0 = Low (no competitive impact)",
    "bUseVSync":              "False = Off (eliminates input lag)",
    "FrameRateLimit":         "0.000000 = Uncapped",
    "FullscreenMode":         "0 = Exclusive Fullscreen (lowest input lag)",
}


def _backup_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "backups")
    os.makedirs(path, exist_ok=True)
    return path


class ValorantConfig:

    def find_config_path(self) -> str:
        local = os.environ.get("LOCALAPPDATA", "")
        if not local:
            return None
        # Resolve and normalise both sides to guard against path traversal via
        # a manipulated LOCALAPPDATA env var.
        local_real = os.path.normcase(os.path.normpath(os.path.realpath(local)))
        base = os.path.normpath(os.path.join(local, "VALORANT", "Saved", "Config"))
        if not os.path.normcase(base).startswith(local_real):
            return None

        if not os.path.isdir(base):
            return None

        # Check direct subfolder names (Windows or WindowsClient)
        for folder_name in ("Windows", "WindowsClient"):
            direct = os.path.join(base, folder_name, "GameUserSettings.ini")
            if os.path.isfile(direct):
                return direct

        # Hash-subfolder path: Config\<hash>\Windows|WindowsClient\GameUserSettings.ini
        for entry in os.listdir(base):
            for folder_name in ("Windows", "WindowsClient"):
                candidate = os.path.join(base, entry, folder_name, "GameUserSettings.ini")
                # Validate resolved path stays within expected base directory
                real_candidate = os.path.normcase(os.path.realpath(candidate))
                if not real_candidate.startswith(local_real):
                    continue
                if os.path.isfile(candidate):
                    return candidate

        return None

    def read_settings(self) -> dict:
        """Returns dict of {key: current_value} for all COMPETITIVE_SETTINGS keys."""
        path = self.find_config_path()
        if not path:
            return {}
        try:
            parser = configparser.RawConfigParser()
            parser.optionxform = str  # preserve case
            parser.read(path, encoding="utf-8")
            result = {}
            for key in COMPETITIVE_SETTINGS:
                for section in parser.sections():
                    if parser.has_option(section, key):
                        result[key] = parser.get(section, key)
                        break
            return result
        except Exception:
            return {}

    def backup_config(self) -> tuple:
        path = self.find_config_path()
        if not path:
            return False, "Valorant config file not found. Is Valorant installed?"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(_backup_dir(), f"valorant_config_{timestamp}.ini")
        try:
            shutil.copy2(path, dest)
            return True, dest
        except Exception as e:
            return False, str(e)

    def apply_competitive_settings(self) -> tuple:
        path = self.find_config_path()
        if not path:
            return False, "Valorant config file not found. Launch Valorant once to generate it."

        # Backup first
        ok, backup_result = self.backup_config()
        if not ok:
            return False, f"Backup failed: {backup_result}"

        try:
            parser = configparser.RawConfigParser()
            parser.optionxform = str
            parser.read(path, encoding="utf-8")

            target_section = None
            for section in parser.sections():
                if "ShooterGameUserSettings" in section or "GameUserSettings" in section:
                    target_section = section
                    break

            if not target_section:
                # If section not found, write to first section or create default
                if parser.sections():
                    target_section = parser.sections()[0]
                else:
                    target_section = "/Script/ShooterGame.ShooterGameUserSettings"
                    parser.add_section(target_section)

            applied = []
            for key, value in COMPETITIVE_SETTINGS.items():
                # Find which section has this key, or write to target section
                wrote = False
                for section in parser.sections():
                    if parser.has_option(section, key):
                        parser.set(section, key, value)
                        wrote = True
                        break
                if not wrote:
                    parser.set(target_section, key, value)
                applied.append(key)

            with open(path, "w", encoding="utf-8") as f:
                parser.write(f)

            return True, f"Applied {len(applied)} competitive settings. Backup: {backup_result}"
        except Exception as e:
            return False, str(e)

    def restore_latest_backup(self) -> tuple:
        bd = _backup_dir()
        backups = sorted(
            [f for f in os.listdir(bd) if f.startswith("valorant_config_") and f.endswith(".ini")],
            reverse=True
        )
        if not backups:
            return False, "No Valorant config backups found."
        path = self.find_config_path()
        if not path:
            return False, "Valorant config path not found."
        try:
            shutil.copy2(os.path.join(bd, backups[0]), path)
            return True, f"Restored from {backups[0]}."
        except Exception as e:
            return False, str(e)

    # ── Fullscreen Optimization ───────────────────────────────────────────────

    def _find_valorant_exe(self):
        candidates = [
            r"C:\Riot Games\VALORANT\live\VALORANT.exe",
            r"D:\Riot Games\VALORANT\live\VALORANT.exe",
            r"E:\Riot Games\VALORANT\live\VALORANT.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game valorant.live",
                0, winreg.KEY_READ
            ) as k:
                loc, _ = winreg.QueryValueEx(k, "InstallLocation")
                exe = os.path.join(loc, "VALORANT.exe")
                if os.path.isfile(exe):
                    return exe
        except Exception:
            pass
        return None

    def get_fullscreen_opt_status(self) -> str:
        val_exe = self._find_valorant_exe()
        if not val_exe:
            return "Valorant.exe not found"
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, val_exe)
                if "DISABLEDXMAXIMIZEDWINDOWEDMODE" in val.upper():
                    return "Disabled (optimized)"
        except Exception:
            pass
        return "Enabled (default)"

    def disable_fullscreen_optimizations(self) -> tuple:
        val_exe = self._find_valorant_exe()
        if not val_exe:
            return False, "Could not find Valorant.exe — launch the game once to register it."
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, val_exe, 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
            return True, f"Fullscreen optimizations disabled for {os.path.basename(val_exe)} — lower input latency in exclusive fullscreen."
        except Exception as e:
            return False, str(e)

    def enable_fullscreen_optimizations(self) -> tuple:
        val_exe = self._find_valorant_exe()
        if not val_exe:
            return False, "Could not find Valorant.exe."
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, val_exe)
                except FileNotFoundError:
                    pass
            return True, "Fullscreen optimizations restored to Windows default."
        except Exception as e:
            return False, str(e)

    def get_setting_display(self) -> list:
        """Returns list of dicts for UI table rendering."""
        current = self.read_settings()
        rows = []
        for key, recommended in COMPETITIVE_SETTINGS.items():
            cur_val = current.get(key, "Not found")
            rows.append({
                "key":         key,
                "name":        SETTING_LABELS.get(key, key),
                "current":     cur_val,
                "recommended": recommended,
                "note":        SETTING_NOTES.get(key, ""),
                "matches":     cur_val.lower() == recommended.lower(),
            })
        return rows

    # ── Crosshair Backup / Restore ────────────────────────────────────────────

    def get_crosshair_code(self) -> str | None:
        """Read CrosshairProfileSettings from GameUserSettings.ini."""
        path = self.find_config_path()
        if not path:
            return None
        try:
            cfg = configparser.RawConfigParser()
            cfg.optionxform = str
            cfg.read(path, encoding="utf-8")
            section = "/Script/ShooterGame.ShooterGameUserSettings"
            if cfg.has_option(section, "CrosshairProfileSettings"):
                return cfg.get(section, "CrosshairProfileSettings")
        except Exception:
            pass
        return None

    def set_crosshair_code(self, code: str) -> tuple:
        """Write CrosshairProfileSettings to GameUserSettings.ini."""
        path = self.find_config_path()
        if not path:
            return False, "Config file not found — launch Valorant once to generate it."
        self.backup_config()
        try:
            cfg = configparser.RawConfigParser()
            cfg.optionxform = str
            cfg.read(path, encoding="utf-8")
            section = "/Script/ShooterGame.ShooterGameUserSettings"
            if not cfg.has_section(section):
                return False, "Section not found in config — launch Valorant once to generate it."
            cfg.set(section, "CrosshairProfileSettings", code)
            with open(path, "w", encoding="utf-8") as f:
                cfg.write(f)
            return True, "Crosshair applied — restart Valorant to see changes."
        except Exception as e:
            return False, str(e)
