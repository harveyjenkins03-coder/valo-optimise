# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

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
        exe = sys.executable
        # Prefer pythonw.exe so no console window opens alongside the GUI
        pythonw = exe.replace("python.exe", "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, f'"{script}"',
            os.path.dirname(script), 1
        )
        if ret > 32:
            # Elevated process launched successfully — exit this non-admin copy
            sys.exit(0)
        else:
            # UAC was denied or elevation failed — exit with error rather than
            # continuing in limited mode where registry writes silently fail
            print("ERROR: Administrator privileges are required. Please accept the UAC prompt.")
            sys.exit(1)


def get_admin_status_label() -> str:
    return "Administrator" if is_admin() else "Limited Mode"
