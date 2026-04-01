# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import os
import subprocess
import ctypes
import winreg
import logging
import psutil

_log = logging.getLogger("valo_optimise.system")


# Processes we must NEVER touch — game anti-cheat and critical OS processes
# All entries MUST be lowercase — kill checks compare with .lower()
PROTECTED_PROCESSES = {
    # Valorant + Vanguard
    "valorant.exe",
    "valorant-win64-shipping.exe",
    "vgc.exe",
    "vgtray.exe",
    "anticheat_helper.exe",
    # Critical Windows OS processes
    "system",
    "svchost.exe",
    "lsass.exe",
    "csrss.exe",
    "winlogon.exe",
    "wininit.exe",
    "services.exe",
    "explorer.exe",
    # This app itself (runs as python.exe / pythonw.exe)
    "python.exe",
    "pythonw.exe",
    # AMD GPU driver processes — killing these causes display crashes
    "atieclxx.exe",
    "atiesrxx.exe",
    "amdow.exe",
    "radeonsoftware.exe",
    "amdrsserv.exe",
    # Discord — keep running alongside Valorant and this app
    "discord.exe",
    "discordhelper.exe",
    "discordcrashhandler.exe",
    "discordptb.exe",
    "discordcanary.exe",
}

# Background processes safe to kill for gaming
BACKGROUND_TARGETS = [
    "GameBarFTServer.exe",
    "XboxGameOverlay.exe",
    "GameBar.exe",
    "OneDrive.exe",
    "SearchIndexer.exe",
    "SearchHost.exe",
    "SearchApp.exe",
    "msedgewebview2.exe",
    "MicrosoftEdgeUpdate.exe",
]


class SystemOptimizer:

    # ── Power Plans ─────────────────────────────────────────────────────────

    def get_current_power_plan(self) -> str:
        try:
            import re
            result = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=10
            )
            line = result.stdout.strip()
            # Extract plan name from parentheses: "Power Scheme GUID: xxx  (Plan Name)"
            match = re.search(r'\(([^)]+)\)\s*$', line)
            if match:
                return match.group(1)
            return line or "Unknown"
        except Exception as e:
            _log.debug("Failed to get power plan: %s", e)
            return "Unknown"

    def get_available_power_plans(self) -> list:
        plans = []
        try:
            result = subprocess.run(
                ["powercfg", "/list"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if "Power Scheme GUID" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        rest = parts[1].strip()
                        guid_and_name = rest.split()
                        guid = guid_and_name[0] if guid_and_name else ""
                        name_part = " ".join(guid_and_name[1:])
                        name = name_part.strip("() ").strip("*").strip()
                        active = "*" in line
                        plans.append({"guid": guid, "name": name, "active": active})
        except Exception:
            pass
        return plans

    def set_high_performance_plan(self) -> tuple:
        try:
            result = subprocess.run(
                ["powercfg", "/setactive", "SCHEME_MIN"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return True, "Power plan set to High Performance."
            # Fallback: find by name
            return self._activate_plan_by_name("High Performance")
        except Exception as e:
            return False, str(e)

    def set_ultimate_performance_plan(self) -> tuple:
        ULTIMATE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"
        plans = self.get_available_power_plans()
        for p in plans:
            if "ultimate" in p["name"].lower():
                try:
                    subprocess.run(
                        ["powercfg", "/setactive", p["guid"]],
                        capture_output=True, text=True, timeout=10
                    )
                    return True, f"Power plan set to {p['name']}."
                except Exception as e:
                    return False, str(e)
        # Create Ultimate Performance plan
        try:
            subprocess.run(
                ["powercfg", "/duplicatescheme", ULTIMATE_GUID],
                capture_output=True, text=True, timeout=15
            )
            plans = self.get_available_power_plans()
            for p in plans:
                if "ultimate" in p["name"].lower():
                    subprocess.run(
                        ["powercfg", "/setactive", p["guid"]],
                        capture_output=True, text=True, timeout=10
                    )
                    return True, "Ultimate Performance plan created and activated."
            return False, "Could not activate Ultimate Performance plan."
        except Exception as e:
            return False, str(e)

    def _activate_plan_by_name(self, name_fragment: str) -> tuple:
        plans = self.get_available_power_plans()
        for p in plans:
            if name_fragment.lower() in p["name"].lower():
                try:
                    subprocess.run(
                        ["powercfg", "/setactive", p["guid"]],
                        capture_output=True, text=True, timeout=10
                    )
                    return True, f"Power plan set to {p['name']}."
                except Exception as e:
                    return False, str(e)
        return False, f"Power plan '{name_fragment}' not found."

    # ── Background Processes ─────────────────────────────────────────────────

    def get_background_processes(self) -> list:
        found = []
        target_lower = {t.lower() for t in BACKGROUND_TARGETS}
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pname = proc.info["name"] or ""
                if pname.lower() in target_lower:
                    mem_mb = round(proc.info["memory_info"].rss / 1024 / 1024, 1) if proc.info["memory_info"] else 0.0
                    found.append({"pid": proc.info["pid"], "name": pname, "memory_mb": mem_mb})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def kill_process_by_name(self, process_name: str) -> tuple:
        if process_name.lower() in PROTECTED_PROCESSES:
            return False, f"'{process_name}' is protected and cannot be killed."
        killed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                    proc.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if killed:
            return True, f"Killed {killed} instance(s) of {process_name}."
        return False, f"{process_name} was not running."

    def kill_all_background_targets(self) -> list:
        results = []
        for target in BACKGROUND_TARGETS:
            ok, msg = self.kill_process_by_name(target)
            if ok:
                results.append((target, True, msg))
        return results

    def disable_xbox_game_bar(self) -> tuple:
        messages = []
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)
            messages.append("AppCaptureEnabled set to 0.")
        except Exception as e:
            messages.append(f"GameDVR registry: {e}")

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"System\GameConfigStore",
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)
            messages.append("GameDVR_Enabled set to 0.")
        except Exception as e:
            messages.append(f"GameConfigStore registry: {e}")

        for name in ["GameBarFTServer.exe", "XboxGameOverlay.exe", "GameBar.exe"]:
            self.kill_process_by_name(name)

        return True, " | ".join(messages)

    def disable_search_indexing(self) -> tuple:
        try:
            r1 = subprocess.run(
                ["sc", "stop", "WSearch"],
                capture_output=True, text=True, timeout=15
            )
            r2 = subprocess.run(
                ["sc", "config", "WSearch", "start=", "demand"],
                capture_output=True, text=True, timeout=15
            )
            if r1.returncode in (0, 1060, 1062):  # 1060 = not found, 1062 = not running
                return True, "Windows Search indexing stopped and set to manual start."
            return True, "Search indexing command sent."
        except Exception as e:
            return False, str(e)

    def disable_onedrive_sync(self) -> tuple:
        return self.kill_process_by_name("OneDrive.exe")

    # ── RAM ──────────────────────────────────────────────────────────────────

    def get_ram_usage(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / 1024**3, 1),
            "available_gb": round(vm.available / 1024**3, 1),
            "percent_used": vm.percent,
        }

    def clear_standby_memory(self) -> tuple:
        """
        Clears working set memory from all accessible processes via Windows API.
        This is equivalent to what RAMMap's 'Empty Standby List' does — safe OS-level call.
        """
        # Minimum permissions required by EmptyWorkingSet (MSDN):
        # PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_SET_INFORMATION (0x0200)
        _EMPTY_WS_ACCESS = 0x0400 | 0x0200
        cleared = 0
        errors = 0
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and proc.info["name"].lower() in PROTECTED_PROCESSES:
                continue
            try:
                handle = ctypes.windll.kernel32.OpenProcess(_EMPTY_WS_ACCESS, False, proc.info["pid"])
                if handle:
                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    cleared += 1
            except Exception:
                errors += 1
                continue
        return True, f"Cleared working set for {cleared} processes. ({errors} skipped)"

    # ── GPU Scheduling ────────────────────────────────────────────────────────

    def check_hardware_gpu_scheduling(self) -> str:
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "HwSchMode")
                if val == 2:
                    return "Enabled"
                return "Disabled"
        except FileNotFoundError:
            return "Disabled"
        except Exception:
            return "Unknown"

    # ── Windows Defender Exclusions ───────────────────────────────────────────

    def _get_riot_paths(self) -> list:
        paths = []
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            val_path = os.path.join(local, "VALORANT")
            if os.path.isdir(val_path):
                paths.append(val_path)
        for drive in ["C:", "D:", "E:", "F:"]:
            rg = os.path.join(drive + "\\", "Riot Games")
            if os.path.isdir(rg):
                paths.append(rg)
        vanguard = r"C:\Program Files\Riot Vanguard"
        if os.path.isdir(vanguard):
            paths.append(vanguard)
        return paths

    def get_defender_exclusion_status(self) -> str:
        try:
            r = subprocess.run(
                ["powershell", "-Command",
                 "(Get-MpPreference).ExclusionPath -join '|'"],
                capture_output=True, text=True, timeout=15
            )
            excls = r.stdout.lower()
            if "valorant" in excls or "riot games" in excls:
                return "Excluded (optimized)"
            return "Not excluded"
        except Exception:
            return "Unknown"

    def add_defender_exclusions(self) -> tuple:
        paths = self._get_riot_paths()
        if not paths:
            return False, "Could not detect Valorant installation. Launch Valorant once first."
        added = []
        for path in paths:
            try:
                # Use -EncodedCommand to prevent injection via path characters
                import base64
                ps_cmd = f"Add-MpPreference -ExclusionPath '{path.replace(chr(39), chr(39)*2)}'"
                encoded = base64.b64encode(ps_cmd.encode('utf-16-le')).decode('ascii')
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", encoded],
                    capture_output=True, text=True, timeout=20
                )
                if r.returncode == 0:
                    added.append(os.path.basename(path))
            except Exception:
                pass
        if added:
            return True, f"Defender exclusions added: {', '.join(added)} — no more scan stutters mid-game."
        return False, "Failed to add exclusions. Try running the app as Administrator."

    def remove_defender_exclusions(self) -> tuple:
        paths = self._get_riot_paths()
        for path in paths:
            try:
                import base64
                ps_cmd = f"Remove-MpPreference -ExclusionPath '{path.replace(chr(39), chr(39)*2)}'"
                encoded = base64.b64encode(ps_cmd.encode('utf-16-le')).decode('ascii')
                subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", encoded],
                    capture_output=True, text=True, timeout=20
                )
            except Exception:
                pass
        return True, "Defender exclusions removed. Valorant folders will be scanned again."

    # ── SysMain (SuperFetch) ──────────────────────────────────────────────────

    def get_sysmain_status(self) -> str:
        try:
            r = subprocess.run(["sc", "query", "SysMain"],
                               capture_output=True, text=True, timeout=10)
            output = r.stdout.lower()
            if "running" in output:
                return "Running (default)"
            if "stopped" in output:
                return "Stopped (optimized)"
            return "Unknown"
        except Exception:
            return "Unknown"

    def disable_sysmain(self) -> tuple:
        try:
            subprocess.run(["sc", "stop", "SysMain"],
                           capture_output=True, text=True, timeout=15)
            r = subprocess.run(["sc", "config", "SysMain", "start=", "disabled"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                return True, "SysMain (SuperFetch) stopped and disabled — eliminates random I/O spikes on NVMe."
            return False, f"sc config failed: {r.stderr.strip() or 'requires admin'}"
        except Exception as e:
            return False, str(e)

    def enable_sysmain(self) -> tuple:
        try:
            subprocess.run(["sc", "config", "SysMain", "start=", "auto"],
                           capture_output=True, text=True, timeout=15)
            subprocess.run(["sc", "start", "SysMain"],
                           capture_output=True, text=True, timeout=15)
            return True, "SysMain (SuperFetch) re-enabled and started."
        except Exception as e:
            return False, str(e)

    # ── Hardware Detection ────────────────────────────────────────────────────

    def get_system_info(self) -> dict:
        """Return detected CPU, GPU, RAM, and display info for the hardware card."""
        info = {
            "cpu": "Unknown",
            "gpu": "Unknown",
            "ram_gb": 0,
            "ram_speed": "Unknown",
            "resolution": "Unknown",
        }

        # CPU — from registry (no WMI needed)
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                0, winreg.KEY_READ
            ) as key:
                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                info["cpu"] = name.strip()
        except Exception as e:
            _log.debug("CPU detection failed: %s", e)

        # GPU — from registry display adapters
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000",
                0, winreg.KEY_READ
            ) as key:
                try:
                    desc, _ = winreg.QueryValueEx(key, "DriverDesc")
                    info["gpu"] = desc.strip()
                except Exception:
                    pass
        except Exception:
            # Fallback: enumerate all subkeys
            try:
                base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0, winreg.KEY_READ) as base_key:
                    i = 0
                    while True:
                        try:
                            sub = winreg.EnumKey(base_key, i)
                            if sub.isdigit():
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{base}\\{sub}", 0, winreg.KEY_READ) as sk:
                                    try:
                                        desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                                        if desc and "microsoft" not in desc.lower():
                                            info["gpu"] = desc.strip()
                                            break
                                    except Exception:
                                        pass
                            i += 1
                        except OSError:
                            break
            except Exception:
                pass

        # RAM total
        try:
            vm = psutil.virtual_memory()
            info["ram_gb"] = round(vm.total / 1024**3)
        except Exception:
            pass

        # Resolution — via ctypes GetSystemMetrics
        try:
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            if w and h:
                info["resolution"] = f"{w}×{h}"
        except Exception:
            pass

        return info

    # ── CPU Minimum Frequency ─────────────────────────────────────────────────

    def get_cpu_min_freq_status(self) -> str:
        try:
            r = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMIN"],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.splitlines():
                if "Current AC Power Setting Index:" in line:
                    val = int(line.split(":")[-1].strip(), 16)
                    return f"100% (optimized)" if val >= 100 else f"{val}% (default)"
            return "Unknown"
        except Exception:
            return "Unknown"

    def set_cpu_min_freq_100(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMIN", "100"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU minimum frequency set to 100% — no frequency scaling lag between frames. Higher power draw while active."

    def restore_cpu_min_freq(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "PROCTHROTTLEMIN", "5"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU minimum frequency restored to default (5%)."

    # ── Windows Update ────────────────────────────────────────────────────────

    def get_windows_update_status(self) -> str:
        try:
            r = subprocess.run(["sc", "query", "wuauserv"],
                               capture_output=True, text=True, timeout=10)
            output = r.stdout.lower()
            if "running" in output:
                return "Running (default)"
            if "stopped" in output:
                return "Paused (optimized)"
            return "Unknown"
        except Exception:
            return "Unknown"

    def pause_windows_update(self) -> tuple:
        try:
            subprocess.run(["sc", "stop", "wuauserv"],
                           capture_output=True, text=True, timeout=15)
            r = subprocess.run(["sc", "config", "wuauserv", "start=", "disabled"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return True, "Windows Update stopped — no more background downloads causing CPU/disk spikes mid-game."
            return False, f"sc config failed: {r.stderr.strip() or 'requires admin'}"
        except Exception as e:
            return False, str(e)

    def resume_windows_update(self) -> tuple:
        try:
            subprocess.run(["sc", "config", "wuauserv", "start=", "demand"],
                           capture_output=True, text=True, timeout=10)
            subprocess.run(["sc", "start", "wuauserv"],
                           capture_output=True, text=True, timeout=15)
            return True, "Windows Update service restored and started."
        except Exception as e:
            return False, str(e)

    # ── DiagTrack (Telemetry) ─────────────────────────────────────────────────

    def get_diagtrack_status(self) -> str:
        try:
            r = subprocess.run(["sc", "query", "DiagTrack"],
                               capture_output=True, text=True, timeout=10)
            output = r.stdout.lower()
            if "running" in output:
                return "Running (default)"
            if "stopped" in output:
                return "Stopped (optimized)"
            return "Unknown"
        except Exception:
            return "Unknown"

    def disable_diagtrack(self) -> tuple:
        try:
            subprocess.run(["sc", "stop", "DiagTrack"],
                           capture_output=True, text=True, timeout=15)
            r = subprocess.run(["sc", "config", "DiagTrack", "start=", "disabled"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return True, "Microsoft telemetry (DiagTrack) stopped — removes periodic CPU interrupts during gameplay."
            return False, f"sc config failed: {r.stderr.strip() or 'requires admin'}"
        except Exception as e:
            return False, str(e)

    def enable_diagtrack(self) -> tuple:
        try:
            subprocess.run(["sc", "config", "DiagTrack", "start=", "auto"],
                           capture_output=True, text=True, timeout=10)
            subprocess.run(["sc", "start", "DiagTrack"],
                           capture_output=True, text=True, timeout=15)
            return True, "DiagTrack (telemetry) restored and started."
        except Exception as e:
            return False, str(e)
