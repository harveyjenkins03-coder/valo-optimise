import ctypes
import subprocess
import winreg


class CpuTimerOptimizer:

    def __init__(self):
        self._timer_active = False

    # ── Timer Resolution ──────────────────────────────────────────────────────

    def get_current_timer_resolution(self) -> str:
        """
        Queries current Windows timer resolution via NtQueryTimerResolution.
        Returns human-readable string.
        """
        try:
            min_res  = ctypes.c_ulong(0)
            max_res  = ctypes.c_ulong(0)
            cur_res  = ctypes.c_ulong(0)
            ntdll = ctypes.windll.ntdll
            ntdll.NtQueryTimerResolution(
                ctypes.byref(min_res),
                ctypes.byref(max_res),
                ctypes.byref(cur_res)
            )
            # Resolution is in 100-nanosecond intervals
            current_ms = cur_res.value / 10000.0
            min_ms     = min_res.value / 10000.0  # min = worst (largest interval)
            return f"{current_ms:.1f}ms (default ~{min_ms:.1f}ms)"
        except Exception:
            return "Unknown"

    def get_timer_resolution_ms(self) -> float:
        """Returns current timer resolution in milliseconds."""
        try:
            min_res = ctypes.c_ulong(0)
            max_res = ctypes.c_ulong(0)
            cur_res = ctypes.c_ulong(0)
            ctypes.windll.ntdll.NtQueryTimerResolution(
                ctypes.byref(min_res), ctypes.byref(max_res), ctypes.byref(cur_res)
            )
            return cur_res.value / 10000.0
        except Exception:
            return -1.0

    def set_timer_resolution_1ms(self) -> tuple:
        """
        Sets Windows timer resolution to 1ms via timeBeginPeriod(1).
        Stays active while this process is alive (resets on app close).
        """
        try:
            result = ctypes.windll.winmm.timeBeginPeriod(1)
            if result == 0:  # TIMERR_NOERROR
                self._timer_active = True
                actual = self.get_timer_resolution_ms()
                return True, f"Timer resolution set to 1ms. Current: {actual:.2f}ms. Resets when app closes."
            return False, f"timeBeginPeriod failed with code {result}."
        except Exception as e:
            return False, str(e)

    def restore_timer_resolution(self) -> tuple:
        """Releases the 1ms timer period request."""
        try:
            if self._timer_active:
                ctypes.windll.winmm.timeEndPeriod(1)
                self._timer_active = False
            return True, "Timer resolution restored to Windows default (~15.6ms)."
        except Exception as e:
            return False, str(e)

    def is_timer_optimized(self) -> bool:
        return self._timer_active

    # ── CPU Core Parking ──────────────────────────────────────────────────────

    def get_core_parking_status(self) -> str:
        """
        Queries the CPMINCORES (minimum processor cores percentage) from the current power scheme.
        100 = all cores always active (no parking). 0 = Windows default (park idle cores).
        """
        try:
            result = subprocess.run(
                ["powercfg", "/query", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            ac_value = None
            for line in output.splitlines():
                line = line.strip()
                if "Current AC Power Setting Index:" in line:
                    try:
                        ac_value = int(line.split(":")[-1].strip(), 16)
                    except ValueError:
                        pass
                    break
            if ac_value is None:
                return "Unknown"
            if ac_value >= 100:
                return "Unparked (optimized)"
            return f"Parked — cores active: {ac_value}% (default)"
        except Exception:
            return "Unknown"

    def disable_core_parking(self) -> tuple:
        """Sets minimum CPU cores to 100% so no cores are parked during gameplay."""
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES", "100"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES", "100"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU core parking disabled. All cores stay active — eliminates micro-stutters."

    def enable_core_parking(self) -> tuple:
        """Restores Windows default core parking (0% minimum = park idle cores)."""
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES", "0"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_PROCESSOR", "CPMINCORES", "0"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU core parking restored to Windows default."

    # ── CPU Boost Mode ────────────────────────────────────────────────────────
    # GUIDs: SUB_PROCESSOR = 54533251-..., PERFBOOSTMODE = 45bcc044-...
    _SUB_PROC = "54533251-82be-4824-96c1-47b60b740d00"
    _BOOSTMODE = "45bcc044-d885-43e2-8605-ee0ec6e96b59"

    def _get_active_scheme_guid(self) -> str:
        try:
            r = subprocess.run(["powercfg", "/getactivescheme"],
                               capture_output=True, text=True, timeout=10)
            for part in r.stdout.split():
                if len(part) == 36 and part.count("-") == 4:
                    return part
        except Exception:
            pass
        return None

    def get_boost_mode_status(self) -> str:
        labels = {0: "Disabled", 1: "Enabled (default)", 2: "Aggressive (optimized)",
                  3: "Efficient Aggressive", 4: "Efficient Enabled"}
        scheme = self._get_active_scheme_guid()
        if scheme:
            reg_path = (r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
                        f"\\{scheme}\\{self._SUB_PROC}\\{self._BOOSTMODE}")
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as k:
                    val, _ = winreg.QueryValueEx(k, "ACSettingIndex")
                    return labels.get(val, f"Mode {val}")
            except FileNotFoundError:
                pass  # Key absent = plan default
            except Exception:
                pass
        return "Enabled (default)"

    def set_boost_mode_aggressive(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", self._SUB_PROC, self._BOOSTMODE, "2"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", self._SUB_PROC, self._BOOSTMODE, "2"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU boost set to Aggressive — Ryzen 9 5900X hits max clock instantly. No more ramp-up lag."

    def restore_boost_mode(self) -> tuple:
        cmds = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", self._SUB_PROC, self._BOOSTMODE, "1"],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", self._SUB_PROC, self._BOOSTMODE, "1"],
            ["powercfg", "/setactive", "SCHEME_CURRENT"],
        ]
        for cmd in cmds:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if r.returncode != 0:
                    return False, f"powercfg failed: {r.stderr.strip()}"
            except Exception as e:
                return False, str(e)
        return True, "CPU boost mode restored to default (Enabled)."

    # ── Dynamic Tick ──────────────────────────────────────────────────────────

    def get_dynamic_tick_status(self) -> str:
        try:
            r = subprocess.run(
                ["bcdedit", "/enum", "{current}"],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.splitlines():
                if "disabledynamictick" in line.lower():
                    return "Disabled (optimized)" if "yes" in line.lower() else "Enabled (default)"
            return "Enabled (default)"
        except Exception:
            return "Unknown"

    def disable_dynamic_tick(self) -> tuple:
        try:
            r = subprocess.run(
                ["bcdedit", "/set", "disabledynamictick", "yes"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "Dynamic tick disabled — tighter frame timing consistency. Reboot required."
            return False, f"bcdedit failed: {r.stderr.strip() or r.stdout.strip() or 'requires admin'}"
        except Exception as e:
            return False, str(e)

    def enable_dynamic_tick(self) -> tuple:
        try:
            r = subprocess.run(
                ["bcdedit", "/set", "disabledynamictick", "no"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, "Dynamic tick restored to default. Reboot required."
            return False, f"bcdedit failed: {r.stderr.strip() or r.stdout.strip()}"
        except Exception as e:
            return False, str(e)
