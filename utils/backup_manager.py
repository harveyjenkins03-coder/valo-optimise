import os
import subprocess
import datetime

# Whitelist of registry key prefixes this app is permitted to back up.
# Any path not starting with one of these will be rejected.
_ALLOWED_BACKUP_PREFIXES = (
    # Original system/network tweaks
    "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile",
    "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\GameDVR",
    "HKCU\\System\\GameConfigStore",
    # Mouse optimizer
    "HKCU\\Control Panel\\Mouse",
    # Visual effects optimizer
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VisualEffects",
    "HKCU\\SOFTWARE\\Microsoft\\GameBar",
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
    # Audio optimizer
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AudioSpatial",
    # Startup manager
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
    "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
    "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
    "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
)


def _backup_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def backup_registry_key(key_path: str, backup_name: str) -> tuple:
    """
    Exports a registry key to a .reg file before any modification.
    key_path example: r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
    Returns (success: bool, message: str).
    """
    # Enforce whitelist — only allow backing up known safe paths
    if not any(key_path.upper().startswith(p.upper()) for p in _ALLOWED_BACKUP_PREFIXES):
        return False, f"Security: registry path is not whitelisted for backup."

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = backup_name.replace(" ", "_").replace("\\", "_")
    filename = f"{safe_name}_{timestamp}.reg"
    filepath = os.path.join(_backup_dir(), filename)

    try:
        result = subprocess.run(
            ["reg", "export", key_path, filepath, "/y"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, filepath
        return False, f"reg export failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Backup timed out."
    except Exception as e:
        return False, str(e)


def restore_registry_key(backup_file_path: str) -> tuple:
    """
    Imports a .reg backup file to restore registry state.
    Returns (success: bool, message: str).
    """
    if not os.path.isfile(backup_file_path):
        return False, f"Backup file not found: {backup_file_path}"

    # Path traversal guard — file must resolve to inside the backups directory
    real_path = os.path.realpath(backup_file_path)
    backups_real = os.path.realpath(_backup_dir())
    if not real_path.startswith(backups_real + os.sep):
        return False, "Security: backup file must be inside the backups folder."

    try:
        result = subprocess.run(
            ["reg", "import", backup_file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "Registry restored successfully."
        return False, f"reg import failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Restore timed out."
    except Exception as e:
        return False, str(e)


def list_backups() -> list:
    """
    Returns a list of backup dicts: [{"name": str, "path": str, "created": str}, ...]
    """
    backups = []
    bd = _backup_dir()
    for fname in sorted(os.listdir(bd), reverse=True):
        if fname.endswith(".reg"):
            fpath = os.path.join(bd, fname)
            mtime = os.path.getmtime(fpath)
            created = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            backups.append({"name": fname, "path": fpath, "created": created})
    return backups
