# Valo Optimise — Claude Code Context

## What this project is
A Windows desktop app (Python + CustomTkinter) that optimises a PC for competitive Valorant gameplay.
All optimisations are OS-level only — no game process interaction, no memory reads, fully Vanguard-safe.

## Tech stack
- **GUI**: CustomTkinter (dark theme, navy/red colour palette)
- **Language**: Python 3.10+
- **Platform**: Windows only (uses winreg, ctypes, powershell, subprocess)
- **Entry point**: `main.py` (~2400 lines, all frames defined here)
- **Modules**: `modules/` — one file per feature domain
- **Utils**: `utils/admin_check.py`, `utils/backup_manager.py`
- **Config**: `config.json` (auto-generated, gitignored)
- **Profiles**: `sensitivity_profiles.json` (gitignored)

## Architecture
- `App` class in `main.py` owns the sidebar nav + content area
- Each tab is a `ctk.CTkFrame` subclass (e.g. `SystemFrame`, `NetworkFrame`)
- All registry/system calls run in background threads via `run_in_thread(func, callback)`
- Results are logged to a `CTkTextbox` status log in each frame
- Admin elevation: `utils/admin_check.require_admin()` called at startup — relaunches with UAC

## Colour palette
```python
BG      = "#0a0e1a"   # deep navy black
PANEL   = "#111827"   # card background
PANEL2  = "#1c2a3a"   # subtle highlight
ACCENT  = "#ff4655"   # Valorant red
ACCENT2 = "#00d4aa"   # teal (success/active)
GREEN   = "#00d4aa"
GOLD    = "#ffd700"
TEXT    = "#f0f4ff"
MUTED   = "#6b7a99"
```

## Nav items (in order)
dashboard, system, network, registry, boost, valorant, mouse, mousedriver, visual, audio, cpu, gpu, visibility, startup, stats, guide

## Key modules
| File | Purpose |
|------|---------|
| `modules/system_optimizer.py` | Power plans, RAM, background processes, CPU freq, Windows Update, DiagTrack |
| `modules/network_optimizer.py` | DNS, NIC power, TCP tweaks, ping test |
| `modules/registry_tweaks.py` | Registry performance tweaks |
| `modules/mouse_optimizer.py` | Mouse acceleration, USB suspend, USB hub power, eDPI calc |
| `modules/mouse_driver.py` | Polling rate monitor, pointer ballistics, sensitivity profiles, device info |
| `modules/gpu_optimizer.py` | AMD ULPS, AMD Chill, HAGS |
| `modules/visibility_optimizer.py` | AMD native colour registry keys (brightness/contrast/gamma) |
| `modules/audio_optimizer.py` | Windows Sonic disable, MMCSS priority |
| `modules/cpu_timer.py` | Timer resolution, core parking, CPU boost mode, dynamic tick |
| `modules/valorant_config.py` | GameUserSettings.ini editor |
| `modules/startup_manager.py` | Startup program manager |
| `modules/stats_tracker.py` | Match stats tracker |
| `modules/visual_optimizer.py` | Visual effects, game mode, transparency |

## Collaborators
- **harveyjenkins03-coder** (owner) — Claude Code user
- Friend (collaborator) — joins via VS Code Live Share

## Repo
https://github.com/harveyjenkins03-coder/valo-optimise

## Rules
- Never interact with game process memory or inject code
- Never bypass Vanguard — all features must be OS-level only
- Always run registry writes in background threads
- Always backup before modifying user config files
- Keep `config.json` and `sensitivity_profiles.json` gitignored
- Test imports with `python -c "import main"` before committing
