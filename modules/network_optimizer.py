# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import socket
import subprocess
import time
import winreg
from concurrent.futures import ThreadPoolExecutor, as_completed


class NetworkOptimizer:

    VALORANT_SERVERS = {
        "NA (US-East)":    ("206.165.102.1",  80),
        "EU (Frankfurt)":  ("185.50.104.201", 80),
        "AP (Singapore)":  ("45.77.204.130",  80),
        "KR (Seoul)":      ("45.77.31.235",   80),
        "BR (Sao Paulo)":  ("45.77.176.235",  80),
        "LATAM (Miami)":   ("108.61.170.60",  80),
    }

    DNS_PRESETS = {
        "Cloudflare": ("1.1.1.1", "1.0.0.1"),
        "Google":     ("8.8.8.8", "8.8.4.4"),
        "OpenDNS":    ("208.67.222.222", "208.67.220.220"),
    }

    # ── Ping ─────────────────────────────────────────────────────────────────

    def ping_server(self, region: str, host: str, port: int, samples: int = 4) -> dict:
        times = []
        lost = 0
        for _ in range(samples):
            try:
                start = time.perf_counter()
                with socket.create_connection((host, port), timeout=3):
                    elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
            except Exception:
                lost += 1
        if not times:
            return {"region": region, "host": host, "avg_ms": -1, "min_ms": -1, "max_ms": -1, "packet_loss": 100.0}
        return {
            "region": region,
            "host": host,
            "avg_ms": round(sum(times) / len(times), 1),
            "min_ms": round(min(times), 1),
            "max_ms": round(max(times), 1),
            "packet_loss": round(lost / samples * 100, 0),
        }

    def ping_all_servers(self) -> list:
        results = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(self.ping_server, region, host, port): region
                for region, (host, port) in self.VALORANT_SERVERS.items()
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    pass
        return sorted(results, key=lambda r: r["avg_ms"] if r["avg_ms"] >= 0 else 99999)

    # ── TCP Tweaks ────────────────────────────────────────────────────────────

    def get_current_tcp_settings(self) -> dict:
        try:
            result = subprocess.run(
                ["netsh", "interface", "tcp", "show", "global"],
                capture_output=True, text=True, timeout=10
            )
            settings = {}
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    settings[key.strip()] = val.strip()
            return settings
        except Exception:
            return {}

    def apply_tcp_optimizations(self) -> list:
        commands = [
            (["netsh", "interface", "tcp", "set", "global", "autotuninglevel=normal"],
             "Auto-Tuning set to Normal"),
            (["netsh", "interface", "tcp", "set", "global", "chimney=disabled"],
             "TCP Chimney Offload disabled"),
            (["netsh", "interface", "tcp", "set", "global", "dca=enabled"],
             "Direct Cache Access enabled"),
            (["netsh", "interface", "tcp", "set", "global", "netdma=enabled"],
             "NetDMA enabled"),
            (["netsh", "interface", "tcp", "set", "global", "timestamps=disabled"],
             "TCP Timestamps disabled"),
        ]
        results = []
        for cmd, label in commands:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                ok = r.returncode == 0
                results.append((ok, label if ok else f"{label} — {r.stderr.strip()}"))
            except Exception as e:
                results.append((False, f"{label} — {e}"))
        return results

    def revert_tcp_settings(self) -> list:
        commands = [
            (["netsh", "interface", "tcp", "set", "global", "autotuninglevel=normal"],
             "Auto-Tuning reverted to Normal"),
            (["netsh", "interface", "tcp", "set", "global", "chimney=enabled"],
             "TCP Chimney Offload enabled"),
            (["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"],
             "TCP Timestamps enabled"),
        ]
        results = []
        for cmd, label in commands:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                results.append((r.returncode == 0, label))
            except Exception as e:
                results.append((False, str(e)))
        return results

    # ── Network Adapters ──────────────────────────────────────────────────────

    def get_network_adapters(self) -> list:
        adapters = []
        try:
            result = subprocess.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines()[3:]:
                parts = line.split()
                if len(parts) >= 4:
                    state = parts[0]
                    iface_type = parts[2]
                    name = " ".join(parts[3:])
                    if state in ("Enabled", "Connected", "Disconnected"):
                        adapters.append({"name": name, "state": state, "type": iface_type})
        except Exception:
            pass
        return adapters

    # ── Adapter Validation ────────────────────────────────────────────────────

    def _validate_adapter_name(self, adapter_name: str) -> bool:
        """Returns True only if adapter_name matches a known system adapter."""
        known = {a["name"] for a in self.get_network_adapters()}
        return adapter_name in known

    # ── DNS ───────────────────────────────────────────────────────────────────

    def set_dns(self, adapter_name: str, preset_name: str) -> tuple:
        if not self._validate_adapter_name(adapter_name):
            return False, f"Security: '{adapter_name}' is not a recognized network adapter."
        preset = self.DNS_PRESETS.get(preset_name)
        if not preset:
            return False, f"Unknown DNS preset: {preset_name}"
        primary, secondary = preset
        try:
            r1 = subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", f"name={adapter_name}", "static", primary],
                capture_output=True, text=True, timeout=10
            )
            r2 = subprocess.run(
                ["netsh", "interface", "ip", "add", "dns", f"name={adapter_name}", secondary, "index=2"],
                capture_output=True, text=True, timeout=10
            )
            if r1.returncode == 0:
                return True, f"DNS set to {preset_name} ({primary} / {secondary}) on {adapter_name}."
            return False, f"Failed to set DNS: {r1.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def reset_dns(self, adapter_name: str) -> tuple:
        if not self._validate_adapter_name(adapter_name):
            return False, f"Security: '{adapter_name}' is not a recognized network adapter."
        try:
            r = subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", f"name={adapter_name}", "dhcp"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return True, f"DNS reset to DHCP on {adapter_name}."
            return False, r.stderr.strip()
        except Exception as e:
            return False, str(e)

    # ── Nagle's Algorithm ─────────────────────────────────────────────────────

    def _get_tcp_interface_keys(self) -> list:
        keys = []
        try:
            base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0, winreg.KEY_READ) as bk:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(bk, i)
                        keys.append(f"{base}\\{sub}")
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass
        return keys

    def get_nagle_status(self) -> str:
        for key_path in self._get_tcp_interface_keys():
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as k:
                    val, _ = winreg.QueryValueEx(k, "TcpNoDelay")
                    if val == 1:
                        return "Disabled (optimized)"
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return "Enabled (default)"

    def disable_nagle(self) -> tuple:
        keys = self._get_tcp_interface_keys()
        if not keys:
            return False, "No TCP interfaces found in registry."
        count = 0
        for key_path in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                    winreg.KEY_SET_VALUE | winreg.KEY_READ) as k:
                    winreg.SetValueEx(k, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(k, "TcpNoDelay", 0, winreg.REG_DWORD, 1)
                    count += 1
            except Exception:
                continue
        if count:
            return True, f"Nagle's algorithm disabled on {count} interface(s) — packets sent immediately, more consistent ping."
        return False, "Could not write TCP registry keys. Try running as Administrator."

    def enable_nagle(self) -> tuple:
        keys = self._get_tcp_interface_keys()
        count = 0
        for key_path in keys:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                    winreg.KEY_SET_VALUE) as k:
                    for val_name in ("TcpAckFrequency", "TcpNoDelay"):
                        try:
                            winreg.DeleteValue(k, val_name)
                        except FileNotFoundError:
                            pass
                    count += 1
            except Exception:
                continue
        return True, f"Nagle's algorithm restored to default on {count} interface(s)."

    # ── NIC Power Management ──────────────────────────────────────────────────

    # Registry path for NIC device class
    _NIC_CLASS = r"HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4D36E972-E325-11CE-BFC1-08002bE10318}"

    def get_nic_power_status(self) -> str:
        # PnPCapabilities = 24 means power management disabled
        cmd = (
            f"$k='{self._NIC_CLASS}';"
            r"$count=(Get-ChildItem $k -EA SilentlyContinue | Where-Object {"
            r"(Get-ItemProperty $_.PSPath -EA SilentlyContinue).NetCfgInstanceId"
            r"} | Where-Object {"
            r"(Get-ItemProperty $_.PSPath -EA SilentlyContinue).PnPCapabilities -eq 24"
            r"}).Count; $count"
        )
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                               capture_output=True, text=True, timeout=15)
            count = r.stdout.strip()
            if count and count != "0":
                return "Disabled (optimized)"
            return "Enabled (default)"
        except Exception:
            return "Unknown"

    def disable_nic_power_management(self) -> tuple:
        # Set PnPCapabilities=24 on every NIC adapter subkey
        cmd = (
            f"$k='{self._NIC_CLASS}';"
            r"Get-ChildItem $k -EA SilentlyContinue | Where-Object {"
            r"(Get-ItemProperty $_.PSPath -EA SilentlyContinue).NetCfgInstanceId"
            r"} | ForEach-Object {"
            r"Set-ItemProperty $_.PSPath -Name PnPCapabilities -Value 24 -Type DWord -EA SilentlyContinue}"
        )
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return True, "NIC power management disabled — adapter stays fully awake, no random packet loss spikes."
            return False, f"PowerShell error: {r.stderr.strip() or 'requires admin'}"
        except Exception as e:
            return False, str(e)

    def enable_nic_power_management(self) -> tuple:
        # Restore PnPCapabilities=0 (default)
        cmd = (
            f"$k='{self._NIC_CLASS}';"
            r"Get-ChildItem $k -EA SilentlyContinue | Where-Object {"
            r"(Get-ItemProperty $_.PSPath -EA SilentlyContinue).NetCfgInstanceId"
            r"} | ForEach-Object {"
            r"Set-ItemProperty $_.PSPath -Name PnPCapabilities -Value 0 -Type DWord -EA SilentlyContinue}"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=30)
            return True, "NIC power management restored to default."
        except Exception as e:
            return False, str(e)

    def get_current_dns(self, adapter_name: str) -> tuple:
        if not self._validate_adapter_name(adapter_name):
            return "Unknown", ""
        try:
            r = subprocess.run(
                ["netsh", "interface", "ip", "show", "dns", f"name={adapter_name}"],
                capture_output=True, text=True, timeout=10
            )
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            dns_servers = [l for l in lines if l[0].isdigit()]
            primary = dns_servers[0] if len(dns_servers) > 0 else "DHCP"
            secondary = dns_servers[1] if len(dns_servers) > 1 else ""
            return primary, secondary
        except Exception:
            return "Unknown", ""
