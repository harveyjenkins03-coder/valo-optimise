# Privacy Policy — Valo Optimise

**Effective date:** 21 March 2026
**Product:** Valo Optimise
**Owners:** Harvey Jenkins & Tobias Sanders

---

## Overview

Valo Optimise is a Windows desktop application that optimises your PC for
competitive Valorant gameplay. This policy explains what data the application
accesses, how it is used, and what leaves your device.

---

## Data We Do NOT Collect

- We do **not** collect any personal information.
- We do **not** have analytics, telemetry, or crash-reporting.
- We do **not** transmit your hardware specifications, system configuration,
  or registry changes to any server.
- We do **not** store or log your Riot ID or match history anywhere beyond your
  own device.

---

## What Stays on Your Device

The following data is created and stored **locally only** — it never leaves your
machine:

| File | Contents | Location |
|------|----------|----------|
| `config.json` | Your last-used settings (region, power plan, DNS choice) | App folder |
| `sensitivity_profiles.json` | Saved mouse sensitivity profiles | App folder |
| `backups/` | Registry backups taken before tweaks are applied | App folder |

These files are never transmitted and are not accessible to the application owners.

---

## Optional External Connection — Valorant Stats

The **Stats** tab allows you to look up a Riot ID to view match history and MMR.
This feature:

- Is **entirely opt-in** — no lookup happens unless you enter a Riot ID and
  press a button.
- Sends your entered Riot ID and selected region to the public, third-party API
  at `api.henrikdev.xyz` (not affiliated with Riot Games or the application owners).
- Is subject to the [HenrikDev API privacy policy](https://henrikdevapi.com).
- Returns data that is already publicly accessible via Riot Games' own systems.

No stats data is stored, forwarded, or retained by this application.

---

## Registry & System Changes

Valo Optimise reads and writes to the Windows registry and system settings to
apply performance optimisations. All changes:

- Are made **locally on your device only**.
- Are backed up before being applied so they can be reverted.
- Are never transmitted to the application owners or any third party.

---

## Administrator Privileges

The application requests UAC elevation to apply certain system-level tweaks.
This privilege is used solely to modify the registry keys and power settings
listed in each feature. It is not used to access personal files, network
credentials, or any data unrelated to PC optimisation.

---

## Children's Privacy

This application is not directed at children under 13. We do not knowingly
collect any information from children.

---

## Changes to This Policy

If this policy changes materially (e.g. analytics are added in a future version),
users will be notified via the GitHub repository and any relevant distribution
platform.

---

## Contact

If you have questions about this privacy policy, please contact the owners via the
GitHub repository: github.com/harveyjenkins03-coder/valo-optimise

© 2026 Harvey Jenkins & Tobias Sanders. All Rights Reserved.
