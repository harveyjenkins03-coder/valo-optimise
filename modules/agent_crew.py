"""
modules/agent_crew.py
=====================
Valo Optimise Agent Crew — 10 specialised AI business agents.

Agents are loaded from .md files in Valo Workspace/agents/.
Each file uses a simple header format:
    # Agent: <name>
    # Icon:  <emoji>
    # Role:  <one-line role description>
    <blank line>
    <system prompt — the rest of the file>

Uses the OpenAI-compatible REST API configured in paperclip_config.json.
No external Python packages required beyond stdlib.
"""

import os
import json
import datetime
import urllib.request
import urllib.error
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_WORKSPACE   = Path(os.path.expanduser("~")) / "OneDrive" / "Desktop" / "Valo Workspace"
_AGENTS_DIR  = _WORKSPACE / "agents"
_OUTPUTS_DIR = _WORKSPACE / "agent_outputs"
_PC_CFG      = _WORKSPACE / "paperclip_config.json"


# ── Config ────────────────────────────────────────────────────────────────────

def _load_ai_cfg() -> dict:
    try:
        return json.loads(_PC_CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ai_cfg(api_url: str = "", api_key: str = "", model: str = "") -> bool:
    cfg = _load_ai_cfg()
    if api_url:
        cfg["ai_api_url"] = api_url
    if api_key:
        cfg["ai_api_key"] = api_key
    if model:
        cfg["ai_model"] = model
    try:
        _PC_CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ── Agent ─────────────────────────────────────────────────────────────────────

class Agent:
    def __init__(self, name: str, icon: str, role: str,
                 system_prompt: str, filename: str):
        self.name          = name
        self.icon          = icon
        self.role          = role
        self.system_prompt = system_prompt
        self.filename      = filename

    def run(self, task: str) -> str:
        """Call the configured AI API and return the response text."""
        cfg     = _load_ai_cfg()
        api_url = (cfg.get("ai_api_url") or "https://api.openclaw.ai/v1").rstrip("/")
        api_key = cfg.get("ai_api_key") or "no-key"
        model   = cfg.get("ai_model")   or "llama3"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user",   "content": task},
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        body = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            f"{api_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return f"ERROR {e.code}: {err_body[:400]}"
        except urllib.error.URLError as e:
            return (
                f"ERROR: Cannot reach AI server.\n"
                f"URL: {api_url}\n"
                f"Reason: {e.reason}\n\n"
                f"Check your API URL and key in the AI Agents tab."
            )
        except Exception as e:
            return f"ERROR: {e}"

    def save_output(self, task: str, output: str) -> str:
        """Save output to Valo Workspace/agent_outputs/ and return the file path."""
        _OUTPUTS_DIR.mkdir(exist_ok=True)
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{self.name.lower().replace(' ', '_')}_{ts}.md"
        path  = _OUTPUTS_DIR / fname
        content = (
            f"# {self.icon} {self.name}\n\n"
            f"**Task:** {task}\n\n"
            f"**Date:** {datetime.datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
            f"---\n\n{output}"
        )
        path.write_text(content, encoding="utf-8")
        return str(path)

    def __repr__(self):
        return f"Agent({self.name!r})"


# ── Loader ────────────────────────────────────────────────────────────────────

def _parse_agent_file(path: Path) -> "Agent | None":
    try:
        text  = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        name = icon = role = None
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# Agent:"):
                name = stripped[8:].strip()
            elif stripped.startswith("# Icon:"):
                icon = stripped[7:].strip()
            elif stripped.startswith("# Role:"):
                role = stripped[7:].strip()
            # Once we have all three headers, everything after is the system prompt
            if name and icon and role and i > 2:
                body_start = i + 1
                break
        if not (name and icon and role):
            return None
        system_prompt = "\n".join(lines[body_start:]).strip()
        return Agent(
            name=name, icon=icon, role=role,
            system_prompt=system_prompt, filename=path.name,
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
