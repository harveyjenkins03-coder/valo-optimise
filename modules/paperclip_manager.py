"""
modules/paperclip_manager.py
============================
Manages the Paperclip AI agent platform (https://paperclip.ing).

Paperclip is a self-hosted, open-source Node.js + React control plane
that lets you build, hire, and manage AI agents as an autonomous company.

Setup flow
----------
1. Check prerequisites  (Node.js 20+, npm, git)
2. Install pnpm globally if missing
3. git clone paperclip repo to INSTALL_DIR
4. pnpm install + pnpm build
5. pnpm dev  → serves UI + API at http://localhost:3100

No external accounts required. Fully free.
"""

import os
import json
import socket
import subprocess
import threading
import shutil

# ── Paths ─────────────────────────────────────────────────────────────────────
# All Paperclip files live in the Valo Workspace folder (sibling on Desktop).
_WORKSPACE_DIR = os.path.join(
    os.path.expanduser("~"), "OneDrive", "Desktop", "Valo Workspace"
)
INSTALL_DIR = os.path.join(_WORKSPACE_DIR, "paperclip")
CONFIG_FILE  = os.path.join(_WORKSPACE_DIR, "paperclip_config.json")
LOG_FILE     = os.path.join(_WORKSPACE_DIR, "paperclip-server.log")
SERVER_PORT = 3100
SERVER_URL  = f"http://localhost:{SERVER_PORT}"
REPO_URL    = "https://github.com/paperclipai/paperclip.git"


def _run(cmd, *, cwd=None, timeout=300):
    """Run a subprocess, return (returncode, stdout, stderr).
    Uses shell=True on Windows so .CMD wrappers (npm.cmd, pnpm.cmd) work."""
    r = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        shell=True
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


class PaperclipManager:
    """Install, configure and control the Paperclip server."""

    def __init__(self):
        self._proc:        subprocess.Popen | None = None
        self._log_cb:      callable | None         = None
        self._log_thread:  threading.Thread | None = None
        self._cfg:         dict                    = self._load_cfg()

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_cfg(self) -> dict:
        defaults = {
            "ai_provider": "openclaw",
            "ai_api_url":  "",
            "ai_api_key":  "",
        }
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    return {**defaults, **json.load(f)}
        except Exception:
            pass
        return defaults

    def save_config(self, **kwargs) -> bool:
        self._cfg.update({k: v for k, v in kwargs.items()})
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, indent=2)
            return True
        except Exception:
            return False

    def get_config(self) -> dict:
        return dict(self._cfg)

    # ── Prerequisites ─────────────────────────────────────────────────────────

    def check_prerequisites(self) -> list[dict]:
        """Returns [{name, ok, detail}] for Node ≥20, npm, pnpm, git."""
        checks = []

        # Node.js 20+
        try:
            rc, ver, _ = _run(["node", "--version"], timeout=6)
            major = int(ver.lstrip("v").split(".")[0])
            checks.append({"name": "Node.js 20+", "ok": rc == 0 and major >= 20,
                            "detail": ver or "Not found"})
        except Exception:
            checks.append({"name": "Node.js 20+", "ok": False, "detail": "Not installed"})

        # npm / npx
        try:
            rc, ver, _ = _run(["npm", "--version"], timeout=6)
            checks.append({"name": "npm / npx", "ok": rc == 0,
                            "detail": f"v{ver}" if rc == 0 else "Not found"})
        except Exception:
            checks.append({"name": "npm / npx", "ok": False, "detail": "Not found"})

        # pnpm (installable via npm)
        try:
            rc, ver, _ = _run(["pnpm", "--version"], timeout=6)
            checks.append({"name": "pnpm", "ok": rc == 0,
                            "detail": f"v{ver}" if rc == 0 else "Will be installed"})
        except Exception:
            checks.append({"name": "pnpm", "ok": False, "detail": "Will be installed automatically"})

        # git
        try:
            rc, ver, _ = _run(["git", "--version"], timeout=6)
            checks.append({"name": "git", "ok": rc == 0,
                            "detail": ver if rc == 0 else "Not found"})
        except Exception:
            checks.append({"name": "git", "ok": False,
                            "detail": "Not installed — download from git-scm.com"})

        return checks

    def node_and_git_ok(self) -> bool:
        for c in self.check_prerequisites():
            if c["name"] in ("Node.js 20+", "git") and not c["ok"]:
                return False
        return True

    # ── Install ───────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return os.path.exists(os.path.join(INSTALL_DIR, "package.json"))

    def install(self, log_cb=None) -> tuple[bool, str]:
        """
        Full automated setup:
          1. Install pnpm if missing
          2. git clone the Paperclip repo
          3. pnpm install dependencies
          4. pnpm build
        Returns (ok, message).
        """
        def _log(msg: str):
            if log_cb:
                log_cb(msg)

        try:
            os.makedirs(INSTALL_DIR, exist_ok=True)

            # 1. pnpm
            if not _which("pnpm"):
                _log("Installing pnpm globally via npm...")
                rc, out, err = _run(["npm", "install", "-g", "pnpm@latest"], timeout=120)
                if rc != 0:
                    return False, f"pnpm install failed: {err[:200]}"
                _log("pnpm installed.")

            # 2. Clone (or pull)
            if not self.is_installed():
                _log("Cloning Paperclip repository (this may take a minute)...")
                rc, out, err = _run(
                    ["git", "clone", "--depth=1", REPO_URL, INSTALL_DIR],
                    timeout=300
                )
                if rc != 0:
                    return False, f"Clone failed: {err[:300]}"
                _log("Repository cloned.")
            else:
                _log("Pulling latest Paperclip updates...")
                _run(["git", "pull", "--ff-only"], cwd=INSTALL_DIR, timeout=60)

            # 3. pnpm install
            _log("Installing Node.js dependencies (1-3 min)...")
            rc, out, err = _run(["pnpm", "install", "--frozen-lockfile"],
                                  cwd=INSTALL_DIR, timeout=600)
            if rc != 0:
                # Try without frozen lockfile on first install
                _log("Retrying without lockfile flag...")
                rc, out, err = _run(["pnpm", "install"], cwd=INSTALL_DIR, timeout=600)
                if rc != 0:
                    return False, f"pnpm install failed: {err[:300]}"
            _log("Dependencies installed.")

            # 4. Build (non-fatal — dev mode works without it)
            _log("Building Paperclip...")
            rc, _, err = _run(["pnpm", "build"], cwd=INSTALL_DIR, timeout=600)
            if rc != 0:
                _log(f"Build note (dev mode still works): {err[:80]}")
            else:
                _log("Build complete.")

            return True, "Paperclip installed successfully."

        except Exception as exc:
            return False, str(exc)

    def update(self, log_cb=None) -> tuple[bool, str]:
        """Pull latest and reinstall."""
        if not self.is_installed():
            return False, "Not installed — run setup first."

        def _log(m):
            if log_cb:
                log_cb(m)

        try:
            _log("Pulling latest from GitHub...")
            rc, _, err = _run(["git", "pull"], cwd=INSTALL_DIR, timeout=120)
            if rc != 0:
                return False, f"Pull failed: {err[:200]}"
            _log("Running pnpm install...")
            rc, _, err = _run(["pnpm", "install"], cwd=INSTALL_DIR, timeout=600)
            if rc != 0:
                return False, f"pnpm install failed: {err[:200]}"
            _log("Rebuilding...")
            _run(["pnpm", "build"], cwd=INSTALL_DIR, timeout=600)
            return True, "Paperclip updated successfully."
        except Exception as exc:
            return False, str(exc)

    # ── Server lifecycle ──────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def is_port_open(self) -> bool:
        """Check whether something is already listening on SERVER_PORT."""
        try:
            with socket.socket() as s:
                s.settimeout(0.4)
                return s.connect_ex(("localhost", SERVER_PORT)) == 0
        except Exception:
            return False

    def start_server(self, log_cb=None) -> tuple[bool, str]:
        if self.is_running():
            return True, "Already running."
        if not self.is_installed():
            return False, "Not installed — run setup first."

        try:
            self._log_cb = log_cb
            # Use tsx to run TypeScript directly (db package exports TS source)
            tsx = os.path.join(INSTALL_DIR, "server", "node_modules", ".bin", "tsx")
            server_entry = os.path.join(INSTALL_DIR, "server", "src", "index.ts")
            self._proc = subprocess.Popen(
                f'"{tsx}" "{server_entry}"',
                cwd=os.path.join(INSTALL_DIR, "server"),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=True,
            )
            # Stream server output to log callback in background
            self._log_thread = threading.Thread(
                target=self._stream, args=(self._proc,), daemon=True
            )
            self._log_thread.start()
            return True, f"Server starting at {SERVER_URL}"
        except Exception as exc:
            return False, str(exc)

    def _stream(self, proc: subprocess.Popen):
        try:
            for line in proc.stdout:
                if self._log_cb and line.strip():
                    self._log_cb(line.rstrip())
        except Exception:
            pass

    def stop_server(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        self._log_cb = None

    # ── Network helpers ───────────────────────────────────────────────────────

    @staticmethod
    def get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    def get_harvey_url(self) -> str:
        return SERVER_URL

    def get_tobias_url(self) -> str:
        return f"http://{self.get_local_ip()}:{SERVER_PORT}"

    # ── Firewall ──────────────────────────────────────────────────────────────

    _FW_RULE = "Paperclip AI (port 3100)"

    def check_firewall_rule(self) -> bool:
        """Return True if the inbound allow rule for port 3100 exists."""
        rc, out, _ = _run(
            f'netsh advfirewall firewall show rule name="{self._FW_RULE}"',
            timeout=6,
        )
        return rc == 0 and "No rules match" not in out

    def ensure_firewall_rule(self) -> tuple[bool, str]:
        """Add inbound firewall rule for port 3100 (works when app runs as admin)."""
        if self.check_firewall_rule():
            return True, "Firewall rule already active."
        rc, _, err = _run(
            f'netsh advfirewall firewall add rule name="{self._FW_RULE}" '
            f"dir=in action=allow protocol=TCP localport={SERVER_PORT}",
            timeout=10,
        )
        if rc == 0:
            return True, f"Firewall rule added — Tobias can now connect on port {SERVER_PORT}."
        return False, f"Could not add firewall rule: {err[:120]}"
