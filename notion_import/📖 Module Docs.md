# 📖 Module Docs

> Quick reference for every module in the project.

---

## Architecture

```
main.py              — All CTkFrame classes + App class + nav
modules/             — One file per feature domain
utils/               — Shared helpers
config.json          — User settings (gitignored)
sensitivity_profiles.json — Mouse profiles (gitignored)
```

---

## Modules

### system_optimizer.py
Power plans, RAM clear, background process killer, CPU min frequency,
Windows Update pause/resume, DiagTrack stop/start, SysMain, Defender exclusions.

### network_optimizer.py
DNS switching (Cloudflare/Google/Quad9), NIC power management (registry PnPCapabilities=24),
TCP tweaks, ping test to Valorant servers.

### registry_tweaks.py
Safe HKLM/HKCU registry performance tweaks. All tweaks defined as `TWEAKS` list.
Apply all with `apply_all_tweaks()`.

### mouse_optimizer.py
Mouse acceleration (MouseSpeed/Threshold registry), USB Selective Suspend (powercfg),
USB Root Hub power (EnhancedPowerManagementEnabled=0), eDPI calculator, aim trainer launcher.

### mouse_driver.py
- `PollingRateMonitor` — WH_MOUSE_LL hook, counts events/sec over 2s
- `PointerBallistics` — SmoothMouseXCurve/Y registry (1:1 linear)
- `SensitivityProfileManager` — JSON profiles, SPI_SETMOUSESPEED
- `MouseDeviceInfo` — PowerShell Get-PnpDevice, VID/PID from InstanceId
- `RawInputChecker` — Verifies MouseSpeed=0, Threshold=0

### gpu_optimizer.py
AMD only. ULPS (`EnableULPS=0`), Chill (`KMD_EnableChill=0`),
HAGS (`HwSchMode=2` in GraphicsDrivers key). Detects AMD via `ColourFullscreenBrightness_DEF`.

### visibility_optimizer.py
AMD native colour registry: `ColourFullscreenBrightness_DEF`, `ColourFullscreenContrast_DEF`,
`ColourFullscreenGamma_DEF`. Read by AMD driver on exclusive fullscreen entry.
4 presets: Default / Subtle / Competitive / Max Visibility.

### audio_optimizer.py
Windows Sonic disable, AudioSrv check, MMCSS Games task priority
(`GPU Priority=8, Priority=6, Scheduling Category=High`).

### cpu_timer.py
Timer resolution (NtSetTimerResolution 0.5ms), core parking (CPMINCORES),
CPU boost mode (PERFBOOSTMODE), dynamic tick (bcdedit disabledynamictick).

### valorant_config.py
Finds `GameUserSettings.ini` (scans WindowsClient subfolder), reads/writes
competitive settings (shadows=0, VSync=off, FullscreenMode=0 etc.), backup/restore.

### visual_optimizer.py
Visual effects (SystemParametersInfo), Game Mode, transparency disable.

### startup_manager.py
HKCU/HKLM Run registry key manager. List, enable, disable startup entries.

### stats_tracker.py
Match stats tracker — manual entry, stored locally.

### settings_guide.py
Static in-app guide for Valorant settings recommendations.

---

## Key Patterns

```python
# All system calls run in background thread
run_in_thread(func, lambda r: self.after(0, lambda: callback(r)))

# Log results to status box
log_to_box(self.log, message, ok=True/False)

# Admin check at startup
require_admin()  # relaunches with UAC if not elevated

# Config persistence
cfg = load_config()   # loads config.json with defaults
save_config(cfg)      # writes back
```

---

## Colour Palette

```python
BG      = "#0a0e1a"   # deep navy
PANEL   = "#111827"   # card bg
PANEL2  = "#1c2a3a"   # highlight
ACCENT  = "#ff4655"   # Valorant red
ACCENT2 = "#00d4aa"   # teal success
GREEN   = "#00d4aa"
GOLD    = "#ffd700"
TEXT    = "#f0f4ff"
MUTED   = "#6b7a99"
```
