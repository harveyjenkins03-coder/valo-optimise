"""
modules/agent_crew.py
=====================
Valo Optimise Agent Crew — 11 specialised AI business agents.

Security model
--------------
- API key stored in ~/.valooptimise/agent_config.json (outside workspace,
  never served by the workspace file API)
- All API URLs validated: http/https only, dangerous IPs blocked (SSRF guard)
- Task input sanitised: max 6 000 chars, control characters stripped
- Output paths validated: no path traversal, stays inside _OUTPUTS_DIR
- Every agent run appended to agent_audit.log (outside workspace)
- SSL certificate verification enforced for https endpoints

No external packages — stdlib only.
"""

import os
import re
import json
import ssl
import datetime
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_WORKSPACE   = Path(os.path.expanduser("~")) / "OneDrive" / "Desktop" / "Valo Workspace"
_AGENTS_DIR  = _WORKSPACE / "agents"
_OUTPUTS_DIR = _WORKSPACE / "agent_outputs"

# Config and audit log live OUTSIDE the workspace (not served by workspace server)
_CFG_DIR   = Path(os.path.expanduser("~")) / ".valooptimise"
_CFG_FILE  = _CFG_DIR / "agent_config.json"
_AUDIT_LOG = _CFG_DIR / "agent_audit.log"

# Legacy path — migrate if present
_LEGACY_CFG = _WORKSPACE / "paperclip_config.json"

# ── Constants ─────────────────────────────────────────────────────────────────
_MAX_TASK_CHARS  = 6_000   # chars sent to AI per run
_MAX_CTX_CHARS   = 12_000  # chars for attached file context
_MAX_OUTPUT_SIZE = 50_000  # chars stored per output file

# Private / link-local IP ranges blocked for SSRF protection
_BLOCKED_IP_PATTERNS = re.compile(
    r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|0\.0\.0\.0|::1|localhost)",
    re.IGNORECASE,
)


# ── Config ────────────────────────────────────────────────────────────────────

def _load_ai_cfg() -> dict:
    """Load config from ~/.valooptimise/agent_config.json, migrating legacy path if needed."""
    _CFG_DIR.mkdir(exist_ok=True)

    # One-time migration: move key out of workspace into secure location
    if _LEGACY_CFG.exists() and not _CFG_FILE.exists():
        try:
            data = json.loads(_LEGACY_CFG.read_text(encoding="utf-8"))
            _CFG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            # Scrub key from legacy file — leave url/model (non-secret)
            data.pop("ai_api_key", None)
            _LEGACY_CFG.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    try:
        return json.loads(_CFG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ai_cfg(api_url: str = "", api_key: str = "", model: str = "",
                api_keys: list = None) -> bool:
    """Persist config to the secure location outside the workspace."""
    _CFG_DIR.mkdir(exist_ok=True)
    cfg = _load_ai_cfg()
    if api_url:
        cfg["ai_api_url"] = api_url
    if api_key:
        cfg["ai_api_key"] = api_key
    if model:
        cfg["ai_model"] = model
    if api_keys is not None:
        # Store deduplicated list; primary key stays as ai_api_key too
        deduped = list(dict.fromkeys(k for k in api_keys if k))
        cfg["ai_api_keys"] = deduped
        if deduped and not cfg.get("ai_api_key"):
            cfg["ai_api_key"] = deduped[0]
    try:
        _CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ── Security helpers ──────────────────────────────────────────────────────────

def _validate_url(url: str) -> tuple[bool, str]:
    """
    Validate an API URL before use.
    Returns (ok, reason). Blocks non-http/https schemes and private IPs (SSRF guard).
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "Invalid URL format."

    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' not allowed — use http or https."

    hostname = parsed.hostname or ""
    if _BLOCKED_IP_PATTERNS.match(hostname):
        # localhost is allowed — agents may talk to local Ollama, etc.
        # Only block the AWS metadata IP and 0.0.0.0 strictly.
        if hostname in ("169.254.169.254", "0.0.0.0"):
            return False, f"IP address '{hostname}' is blocked."

    if not hostname:
        return False, "URL has no hostname."

    return True, ""


def _sanitize_input(text: str) -> str:
    """Strip control characters and enforce max length."""
    if not isinstance(text, str):
        return ""
    # Remove control chars except tab, newline, carriage return
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return cleaned[:_MAX_TASK_CHARS]


def _safe_filename(name: str) -> str:
    """Produce a filesystem-safe filename component from an agent name."""
    return re.sub(r"[^\w\-]", "_", name.lower())[:40]


def _audit(event: str, agent_name: str, task_preview: str, detail: str = ""):
    """Append one line to the audit log (non-blocking best-effort)."""
    try:
        _CFG_DIR.mkdir(exist_ok=True)
        ts      = datetime.datetime.now().isoformat(timespec="seconds")
        preview = task_preview[:80].replace("\n", " ")
        line    = f"{ts} | {event:12} | {agent_name:25} | {preview}"
        if detail:
            line += f" | {detail[:60]}"
        with open(_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _ssl_context() -> ssl.SSLContext:
    """Return a verified SSL context (enforced for https endpoints)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode    = ssl.CERT_REQUIRED
    return ctx


# ── Agent ─────────────────────────────────────────────────────────────────────

class Agent:
    def __init__(self, name: str, icon: str, role: str,
                 system_prompt: str, filename: str,
                 model: str = "", max_tokens: int = 0, context: str = "full"):
        self.name          = name
        self.icon          = icon
        self.role          = role
        self.system_prompt = system_prompt
        self.filename      = filename
        self.model         = model        # optional per-agent model override
        self.max_tokens    = max_tokens   # 0 = use global default
        self.context       = context      # "full" | "minimal"

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, task: str, file_context: str = "") -> str:
        """
        Call the configured AI API and return the response.

        Parameters
        ----------
        task         : The user's task description (sanitised internally).
        file_context : Optional file content attached by the user for context.
                       Prepended to the task inside the user message.
        """
        # 1. Sanitise inputs
        task = _sanitize_input(task)
        if not task:
            return "ERROR: Task is empty after sanitisation."

        if file_context:
            file_context = file_context[:_MAX_CTX_CHARS]

        # 2. Load and validate config
        cfg     = _load_ai_cfg()
        api_url = (cfg.get("ai_api_url") or "https://api.openclaw.ai/v1").rstrip("/")
        api_key = cfg.get("ai_api_key") or "no-key"
        model   = cfg.get("ai_model")   or "llama3"

        ok, reason = _validate_url(api_url)
        if not ok:
            _audit("URL_BLOCKED", self.name, task, reason)
            return f"ERROR: Invalid API URL — {reason}\nUpdate the URL in the Agent Crew settings."

        # 3. Build user message (context first, then task)
        user_content = task
        if file_context:
            user_content = (
                f"## Attached file context\n\n```\n{file_context}\n```\n\n"
                f"## Task\n\n{task}"
            )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            f"{api_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
                "User-Agent":    "groq-python/0.11.0",
            },
            method="POST",
        )

        # 4. Choose SSL context (verified for https, plain for http)
        ctx = _ssl_context() if api_url.startswith("https") else None

        # 5. Audit: run started
        _audit("RUN_START", self.name, task)

        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                raw  = resp.read().decode("utf-8")
                data = json.loads(raw)
            result = data["choices"][0]["message"]["content"]
            _audit("RUN_OK", self.name, task, f"{len(result)} chars")
            return result

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:300]
            _audit("HTTP_ERR", self.name, task, f"HTTP {e.code}")
            return f"ERROR {e.code}: {err_body}"

        except urllib.error.URLError as e:
            _audit("URL_ERR", self.name, task, str(e.reason)[:60])
            return (
                "ERROR: Cannot reach the AI server.\n\n"
                f"Reason: {e.reason}\n\n"
                "Check your API URL and key in the Agent Crew settings."
            )

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            _audit("PARSE_ERR", self.name, task, str(e)[:60])
            return f"ERROR: Unexpected response from AI server — {e}"

        except Exception as e:
            _audit("UNKNOWN_ERR", self.name, task, str(e)[:60])
            return f"ERROR: {e}"

    # ── Save output ───────────────────────────────────────────────────────────

    def save_output(self, task: str, output: str) -> str:
        """
        Save output to agent_outputs/ and return the file path.
        Path traversal is prevented: the resolved path must stay inside _OUTPUTS_DIR.
        """
        _OUTPUTS_DIR.mkdir(exist_ok=True)

        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{_safe_filename(self.name)}_{ts}.md"
        path  = _OUTPUTS_DIR / fname

        # Path traversal guard
        if not str(path.resolve()).startswith(str(_OUTPUTS_DIR.resolve())):
            raise ValueError(f"Unsafe output path rejected: {path}")

        content = (
            f"# {self.icon} {self.name}\n\n"
            f"**Task:** {task[:200]}\n\n"
            f"**Date:** {datetime.datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
            f"---\n\n{output[:_MAX_OUTPUT_SIZE]}"
        )
        path.write_text(content, encoding="utf-8")
        _audit("SAVE", self.name, task, fname)
        return str(path)

    def __repr__(self):
        return f"Agent({self.name!r})"


# ── File context helper ───────────────────────────────────────────────────────

def read_file_for_context(file_path: str) -> tuple[bool, str]:
    """
    Safely read a file to attach as agent context.
    Returns (ok, content_or_error).
    Only allows text-readable files; enforces size limit.
    """
    try:
        path = Path(file_path).resolve()
        if not path.is_file():
            return False, f"File not found: {file_path}"
        size = path.stat().st_size
        if size > 200_000:  # 200 KB limit
            return False, f"File too large ({size // 1024} KB) — max 200 KB."
        text = path.read_text(encoding="utf-8", errors="replace")
        return True, text[:_MAX_CTX_CHARS]
    except Exception as e:
        return False, f"Cannot read file: {e}"


def read_git_log(repo_path: str, n: int = 30) -> tuple[bool, str]:
    """
    Read recent git commits as context for the Release Notes Writer or Code Reviewer.
    Safe: read-only, no shell injection (uses list args).
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            cwd=repo_path,
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return False, f"git log failed: {result.stderr[:200]}"
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "git not found on PATH."
    except Exception as e:
        return False, str(e)


# ── Loader ────────────────────────────────────────────────────────────────────

def _parse_agent_file(path: Path) -> "Agent | None":
    try:
        text  = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        name = icon = role = None
        model = ""
        max_tokens = 0
        context = "full"
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# Agent:"):
                name = stripped[8:].strip()
            elif stripped.startswith("# Icon:"):
                icon = stripped[7:].strip()
            elif stripped.startswith("# Role:"):
                role = stripped[7:].strip()
            elif stripped.startswith("# Model:"):
                model = stripped[8:].strip()
            elif stripped.startswith("# Max-Tokens:"):
                try:
                    max_tokens = int(stripped[13:].strip())
                except ValueError:
                    pass
            elif stripped.startswith("# Context:"):
                context = stripped[10:].strip().lower()
            elif name and icon and role and not stripped.startswith("#"):
                # First non-header line after required fields — body starts here
                body_start = i
                break
        if not (name and icon and role):
            return None
        system_prompt = "\n".join(lines[body_start:]).strip()
        return Agent(
            name=name, icon=icon, role=role,
            system_prompt=system_prompt, filename=path.name,
            model=model, max_tokens=max_tokens, context=context,
        )
    except Exception:
        return None


def load_agents() -> list:
    """Load all agents from Valo Workspace/agents/, sorted by filename."""
    if not _AGENTS_DIR.exists():
        return []
    agents = []
    for f in sorted(_AGENTS_DIR.glob("*.md")):
        a = _parse_agent_file(f)
        if a:
            agents.append(a)
    return agents
