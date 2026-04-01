# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import winreg
from utils import backup_manager


# All registry paths are whitelisted here — no free-form registry editing
MMCSS_GAMES    = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
SYSTEM_PROFILE = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
TCPIP_PARAMS   = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"

TWEAKS = [
    {
        "id": "mmcss_gpu_priority",
        "name": "MMCSS GPU Priority",
        "description": "Raises GPU scheduling priority to 8 for game tasks (default 2). Reduces GPU task switch overhead.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": MMCSS_GAMES,
        "value_name": "GPU Priority",
        "value_data": 8,
        "value_type": winreg.REG_DWORD,
        "default": 2,
    },
    {
        "id": "mmcss_priority",
        "name": "MMCSS Task Priority",
        "description": "Raises CPU scheduling priority to 6 for game tasks (default 2). More CPU time for your game.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": MMCSS_GAMES,
        "value_name": "Priority",
        "value_data": 6,
        "value_type": winreg.REG_DWORD,
        "default": 2,
    },
    {
        "id": "mmcss_scheduling_category",
        "name": "MMCSS Scheduling Category",
        "description": "Sets scheduling category to 'High' for game tasks. Ensures timely CPU time allocation.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": MMCSS_GAMES,
        "value_name": "Scheduling Category",
        "value_data": "High",
        "value_type": winreg.REG_SZ,
        "default": "Medium",
    },
    {
        "id": "network_throttling_off",
        "name": "Disable Network Throttling",
        "description": "Removes Windows' 10-packet network throttle for multimedia/game traffic. Reduces ping spikes.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": SYSTEM_PROFILE,
        "value_name": "NetworkThrottlingIndex",
        "value_data": 0xFFFFFFFF,
        "value_type": winreg.REG_DWORD,
        "default": 10,
    },
    {
        "id": "system_responsiveness",
        "name": "System Responsiveness",
        "description": "Sets CPU time reserved for background tasks to 0% (default 20%). More CPU for your game.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": SYSTEM_PROFILE,
        "value_name": "SystemResponsiveness",
        "value_data": 0,
        "value_type": winreg.REG_DWORD,
        "default": 20,
    },
    {
        "id": "tcp_ack_frequency",
        "name": "TCP ACK Frequency",
        "description": "Sends TCP acknowledgements immediately (1) instead of every 2 packets. Reduces network latency.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": TCPIP_PARAMS,
        "value_name": "TcpAckFrequency",
        "value_data": 1,
        "value_type": winreg.REG_DWORD,
        "default": 2,
    },
    {
        "id": "tcp_no_delay",
        "name": "TCP No Delay (Nagle Off)",
        "description": "Disables Nagle's algorithm at the registry level. Sends packets immediately, reducing latency.",
        "hive": winreg.HKEY_LOCAL_MACHINE,
        "hive_label": "HKLM",
        "key": TCPIP_PARAMS,
        "value_name": "TCPNoDelay",
        "value_data": 1,
        "value_type": winreg.REG_DWORD,
        "default": 0,
    },
]


class RegistryTweaks:

    def _read_value(self, hive, key_path: str, value_name: str):
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, value_name)
                return val
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _write_value(self, hive, key_path: str, value_name: str, value_data, value_type) -> tuple:
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, value_name, 0, value_type, value_data)
            return True, "OK"
        except PermissionError:
            return False, "Permission denied — run as Administrator."
        except Exception as e:
            return False, str(e)

    def get_tweak_status(self, tweak_id: str) -> dict:
        tweak = next((t for t in TWEAKS if t["id"] == tweak_id), None)
        if not tweak:
            return {"id": tweak_id, "status": "Error", "is_applied": False}
        current = self._read_value(tweak["hive"], tweak["key"], tweak["value_name"])
        is_applied = current == tweak["value_data"]
        return {
            "id": tweak["id"],
            "name": tweak["name"],
            "description": tweak["description"],
            "current_value": current,
            "optimized_value": tweak["value_data"],
            "default_value": tweak["default"],
            "is_applied": is_applied,
            "status": "Applied" if is_applied else "Default",
        }

    def get_all_tweak_statuses(self) -> list:
        return [self.get_tweak_status(t["id"]) for t in TWEAKS]

    def apply_tweak(self, tweak_id: str) -> tuple:
        tweak = next((t for t in TWEAKS if t["id"] == tweak_id), None)
        if not tweak:
            return False, f"Unknown tweak: {tweak_id}"

        # Backup first — always
        key_label = tweak["hive_label"] + "\\" + tweak["key"].split("\\")[-1]
        full_key = tweak["hive_label"] + "\\" + tweak["key"]
        ok, backup_path = backup_manager.backup_registry_key(full_key, tweak["id"])
        if not ok:
            return False, f"Backup failed: {backup_path}"

        write_ok, msg = self._write_value(
            tweak["hive"], tweak["key"], tweak["value_name"],
            tweak["value_data"], tweak["value_type"]
        )
        if write_ok:
            return True, f"{tweak['name']} applied. Backup: {backup_path}"
        return False, f"{tweak['name']} failed: {msg}"

    def apply_all_tweaks(self) -> list:
        return [(t["id"],) + self.apply_tweak(t["id"]) for t in TWEAKS]

    def revert_tweak(self, tweak_id: str) -> tuple:
        tweak = next((t for t in TWEAKS if t["id"] == tweak_id), None)
        if not tweak:
            return False, f"Unknown tweak: {tweak_id}"
        write_ok, msg = self._write_value(
            tweak["hive"], tweak["key"], tweak["value_name"],
            tweak["default"], tweak["value_type"]
        )
        if write_ok:
            return True, f"{tweak['name']} reverted to default."
        return False, f"Revert failed: {msg}"

    def revert_all_tweaks(self) -> list:
        return [(t["id"],) + self.revert_tweak(t["id"]) for t in TWEAKS]
