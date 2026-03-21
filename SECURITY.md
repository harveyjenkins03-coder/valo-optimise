# Security Notes

## Workspace password
`workspace/workspace.cfg` holds the plaintext workspace password (hashed at compare
time using SHA-256). **Change the `PASSWORD` value before sharing access with
anyone outside your immediate team.** The file is gitignored and must never be
committed.

## Session secret
The `SESSION_SECRET` in `workspace/workspace.cfg` signs Flask session cookies.
Rotate it whenever you suspect it has been exposed or after revoking a
collaborator's access.

## ngrok / tunnel tokens
ngrok auth tokens should be treated as single-session credentials:
- Regenerate the token in the ngrok dashboard after each collaborative session.
- Never commit `.env` files or any file containing the ngrok auth token.

## config.json / local settings
`config.json` and `sensitivity_profiles.json` contain machine-local settings and
are gitignored. Do not commit them — they may expose local file paths or personal
configuration.

## Registry operations
Several optimisation modules write directly to the Windows registry
(HKEY_LOCAL_MACHINE and HKEY_CURRENT_USER). The app requests UAC elevation only
when needed. **Never run untrusted scripts as Administrator** — only run this tool
from the project's own source that you have reviewed.

## Reporting issues
If you discover a security issue in this project, please report it privately to
the project owner rather than opening a public issue.
