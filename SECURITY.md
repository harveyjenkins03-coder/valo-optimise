# Security Policy — Valo Optimise

**Owners:** Harvey Jenkins & Tobias Sanders

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | Yes |
| Older releases | No — always update to latest |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Report security issues privately via a GitHub Security Advisory:
https://github.com/harveyjenkins03-coder/valo-optimise/security/advisories/new

We aim to acknowledge reports within 48 hours and provide a fix within 14 days.

---

## Security Design

### Registry Operations
Valo Optimise writes to the Windows registry to apply performance tweaks. The
utils/backup_manager.py module enforces a strict whitelist of allowed registry
paths — no code may write to a path not explicitly permitted in that whitelist.

### Admin Elevation
The app requests UAC elevation at startup, used only to modify the specific
registry keys and power settings required for each feature. It is not used to
access personal data, credentials, or unrelated system areas.

### No Background Network Calls
The application makes no background network requests. The only outbound connection
is the user-initiated Valorant stats lookup to the public third-party API
api.henrikdev.xyz. All connections use HTTPS with SSL verification enabled.

### Local Data Only
All settings, profiles, and backups are stored locally. No data is transmitted
to the owners or any analytics service. See PRIVACY.md for full details.

---

## Code Integrity

Only authorised owners (Harvey Jenkins & Tobias Sanders) may merge changes into
the master branch. Branch protection rules require pull request reviews before
merging. No direct pushes to the protected branch are permitted.

If you obtained this software from a source other than the official GitHub
repository or an authorised distribution platform, it may have been tampered with.

---

## Sensitive Files

config.json and sensitivity_profiles.json are gitignored and must never be
committed. Registry backups in backups/ are also gitignored.

---

(c) 2026 Harvey Jenkins & Tobias Sanders. All Rights Reserved.
