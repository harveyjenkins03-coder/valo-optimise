import os
import json
import winreg


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DISABLED_FILE = os.path.join(_ROOT, "disabled_startup.json")

# System paths — entries whose command contains these are protected and cannot be disabled.
# Includes Windows system paths AND Riot/Vanguard paths to prevent accidentally disabling
# the anti-cheat kernel service, which would prevent Valorant from launching.
_PROTECTED_PATHS = (
    "\\windows\\system32\\",
    "\\windows\\syswow64\\",
    "\\windows\\system\\",
    "\\riot vanguard\\",   # Vanguard kernel-mode anti-cheat service
    "\\riot games\\",      # Riot Client and associated launchers
)

_HIVES = [
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKLM"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU (RunOnce)"),
]


def _is_protected(command: str) -> bool:
    cmd_lower = command.lower()
    return any(p in cmd_lower for p in _PROTECTED_PATHS)


def _load_disabled() -> dict:
    try:
        if os.path.isfile(_DISABLED_FILE):
            with open(_DISABLED_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_disabled(data: dict):
    try:
        with open(_DISABLED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class StartupManager:

    def get_startup_entries(self) -> list:
        """Returns all startup entries from registry Run keys."""
        entries = []
        disabled = _load_disabled()

        for hive, key_path, label in _HIVES:
            try:
                with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            protected = _is_protected(value)
                            entries.append({
                                "name":      name,
                                "command":   value,
                                "hive":      label,
                                "key_path":  key_path,
                                "hive_const": hive,
                                "protected": protected,
                                "enabled":   True,
                            })
                            i += 1
                        except OSError:
                            break
            except Exception:
                continue

        # Append disabled entries from JSON
        for key, info in disabled.items():
            entries.append({
                "name":      info.get("name", key),
                "command":   info.get("command", ""),
                "hive":      info.get("label", ""),
                "key_path":  info.get("key_path", ""),
                "hive_const": None,
                "protected": False,
                "enabled":   False,
            })

        return entries

    def disable_entry(self, name: str, hive_const, key_path: str, label: str) -> tuple:
        """Saves entry to disabled_startup.json and deletes registry value."""
        try:
            with winreg.OpenKey(hive_const, key_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except Exception:
            return False, f"Could not read '{name}' from registry."

        if _is_protected(value):
            return False, f"'{name}' is a protected system entry and cannot be disabled."

        disabled = _load_disabled()
        disabled[name] = {
            "name":     name,
            "command":  value,
            "label":    label,
            "key_path": key_path,
            "hive_id":  "HKCU" if hive_const == winreg.HKEY_CURRENT_USER else "HKLM",
        }
        _save_disabled(disabled)

        try:
            with winreg.OpenKey(hive_const, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
            return True, f"'{name}' disabled and saved for re-enabling."
        except Exception as e:
            return False, str(e)

    def enable_entry(self, name: str) -> tuple:
        """Restores a previously disabled entry to the registry."""
        disabled = _load_disabled()
        if name not in disabled:
            return False, f"'{name}' not found in disabled entries."

        info = disabled[name]
        hive_const = (
            winreg.HKEY_CURRENT_USER if info.get("hive_id") == "HKCU"
            else winreg.HKEY_LOCAL_MACHINE
        )
        key_path = info["key_path"]
        command  = info["command"]

        try:
            with winreg.OpenKey(hive_const, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        except Exception as e:
            return False, f"Could not restore '{name}': {e}"

        del disabled[name]
        _save_disabled(disabled)
        return True, f"'{name}' re-enabled in startup."

    def get_disabled_entries(self) -> list:
        return list(_load_disabled().values())
