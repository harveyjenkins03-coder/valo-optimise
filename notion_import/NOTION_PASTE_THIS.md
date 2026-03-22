# 🏠 Valo Optimise HQ

> Pro performance suite for Valorant. Built by Harvey & Friend.

---

## 🔗 Quick Links

- GitHub Repo → https://github.com/harveyjenkins03-coder/valo-optimise
- Run app → Launch as Admin.bat (double-click)
- Live coding → VS Code Live Share (Harvey starts session)

---

## 👥 Team

| Name | Role |
|------|------|
| Harvey | Lead Dev / Claude Code |
| Friend | Co-Dev |

---

## 📋 Task Board

### 🔴 To Do

- [ ] Live Ping Monitor — Real-time latency graph to Valorant servers (EU/NA/AP)
- [ ] Crosshair Backup/Restore — Extract, save and restore crosshair from game config
- [ ] Auto-Restore on Exit — Re-enable Windows Update + DiagTrack when app closes
- [ ] Settings Export/Import — Package all optimisation settings into a shareable file
- [ ] First-Launch Onboarding — Wizard that runs all safe tweaks on first open
- [ ] Toast Notifications — Windows native notifications when boost completes
- [ ] Global Hotkey — Ctrl+Shift+B triggers Pre-Game Boost from anywhere

### 🟡 In Progress



### 🟢 Done

- [x] System Optimizer — power plans, RAM, background processes, CPU freq, Windows Update, DiagTrack
- [x] Network Optimizer — DNS, NIC power, TCP tweaks, ping test
- [x] Registry Tweaks
- [x] Mouse & Aim — acceleration, USB suspend, USB hub power, eDPI calc, aim trainers
- [x] Mouse Driver — polling rate, 1:1 ballistics, sensitivity profiles, device info, raw input
- [x] GPU Optimizer — AMD ULPS, AMD Chill, HAGS
- [x] Visibility Optimizer — AMD native colour keys
- [x] Audio Optimizer — Windows Sonic, MMCSS priority
- [x] CPU & Timer — timer resolution, core parking, boost mode, dynamic tick
- [x] Valorant Config Editor
- [x] Pre-Game Boost — one-click sequence
- [x] Dashboard landing page
- [x] Premium dark navy GUI redesign
- [x] Admin elevation via UAC
- [x] GitHub repo + VS Code Live Share setup
- [x] Friend setup script
- [x] Notion workspace

---

## 🗺️ Feature Roadmap

### 🚀 High Priority

| Feature | Owner | Notes |
|---------|-------|-------|
| Live Ping Monitor | — | Show latency to EU/NA/AP Valorant servers |
| Crosshair Backup | — | Read from GameUserSettings.ini |
| Auto-Restore on Exit | — | Restore services on app close |
| Global Hotkey | — | Win32 RegisterHotKey API |

### 🟡 Medium Priority

| Feature | Owner | Notes |
|---------|-------|-------|
| Settings Export/Import | — | JSON file with all opt settings |
| Toast Notifications | — | Windows.UI.Notifications |
| First-Launch Onboarding | — | Step-by-step wizard UI |

### 💡 Backlog

| Feature | Notes |
|---------|-------|
| FPS estimator | Based on detected hardware vs benchmarks |
| Auto-launch Valorant after boost | Steam URI |
| Scheduled boost | Windows Task Scheduler |
| Session win/loss tracker | Valorant local match history |
| Light mode toggle | Alternative colour theme |

---

## 🐛 Bug Tracker

| # | Bug | Status |
|---|-----|--------|
| 1 | Valorant config "cannot find file" — WindowsClient subfolder not scanned | ✅ Fixed |
| 2 | NIC power management — `-AllowComputerToTurnOffDevice` invalid PowerShell param | ✅ Fixed |
| 3 | App not running as admin — UAC elevation failing in terminal sessions | ✅ Fixed |

---

## 📝 Session Notes

### Session 1 — Project Foundation
**Built:** Full app — all 14 modules, System/Network/Registry/Mouse/GPU/Visibility/Audio/CPU optimisers, Pre-Game Boost, AMD native colour keys, admin elevation

### Session 2 — Aim Improvement + GUI
**Built:** USB power management, eDPI calc, aim trainers, CPU min freq, Windows Update/DiagTrack, MMCSS, AMD ULPS/Chill/HAGS, Mouse Driver tab, Dashboard, premium GUI, GitHub + Live Share, friend setup, Notion

---

## 📖 Module Docs

### Architecture
- `main.py` — All UI frames + App class + nav (2400+ lines)
- `modules/` — One file per feature
- `utils/` — admin_check.py, backup_manager.py
- `config.json` — User settings (gitignored)
- `sensitivity_profiles.json` — Mouse profiles (gitignored)

### Key Modules
| File | Purpose |
|------|---------|
| system_optimizer.py | Power, RAM, processes, CPU freq, Win Update, DiagTrack |
| network_optimizer.py | DNS, NIC power (PnPCapabilities=24), TCP, ping |
| mouse_optimizer.py | Acceleration, USB suspend, eDPI, aim trainers |
| mouse_driver.py | Polling rate, 1:1 ballistics, profiles, device info |
| gpu_optimizer.py | AMD ULPS, Chill, HAGS |
| visibility_optimizer.py | AMD colour registry keys |
| audio_optimizer.py | Windows Sonic, MMCSS |
| cpu_timer.py | Timer, core parking, boost mode, dynamic tick |
| valorant_config.py | GameUserSettings.ini editor |

### Colour Palette
| Name | Hex |
|------|-----|
| Background | #0a0e1a |
| Panel | #111827 |
| Accent (red) | #ff4655 |
| Success (teal) | #00d4aa |
| Text | #f0f4ff |
| Muted | #6b7a99 |

### Key Code Patterns
All system calls run in background thread via `run_in_thread(func, callback)`
Log results with `log_to_box(self.log, message, ok=True/False)`
Admin check at startup via `require_admin()` — relaunches with UAC if needed
