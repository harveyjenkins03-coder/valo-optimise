# 🐛 Bug Tracker

---

## 🔴 Open

| # | Bug | Reported By | Steps to Reproduce | Status |
|---|-----|-------------|-------------------|--------|
| 1 | Valorant config "cannot find file" — fixed by scanning WindowsClient subfolder | Harvey | Open Valorant Config tab without game launched | ✅ Fixed |
| 2 | NIC power management PowerShell error — `-AllowComputerToTurnOffDevice` invalid param | Harvey | Click Disable NIC Power Management in Network tab | ✅ Fixed |
| 3 | App not running as admin — UAC elevation failing in terminal sessions | Harvey | Run app from VS Code terminal | ✅ Fixed |

---

## 🟢 Fixed



---

## 📝 Notes

- Always test with **Launch as Admin.bat** — many features silently fail without elevation
- Registry writes fail gracefully (return False, error message) — check status log
- Valorant config path: `%LOCALAPPDATA%\VALORANT\Saved\Config\<hash>\WindowsClient\GameUserSettings.ini`
