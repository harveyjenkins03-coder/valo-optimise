import ctypes
import sys
import os


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def require_admin() -> None:
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        # Prefer pythonw.exe so no console window opens alongside the GUI
        exe = sys.executable
        pythonw = exe.replace("python.exe", "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, f'"{script}"',
            os.path.dirname(script), 1
        )
        # ret > 32 means success — exit so the elevated copy takes over
        if ret > 32:
            sys.exit(0)
        # If UAC was denied or failed, continue running without admin


def get_admin_status_label() -> str:
    return "Administrator" if is_admin() else "Limited Mode"
