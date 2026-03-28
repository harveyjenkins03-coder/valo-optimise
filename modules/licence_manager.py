# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
modules/licence_manager.py
===========================
Licence validation for Valo Optimise.

Tiers
-----
free     — no key required, basic tabs only
beta     — time-limited beta key, validated against the Valo validation server
pro      — monthly Gumroad key
lifetime — one-time Gumroad key

Storage
-------
~/.valooptimise/licence.json
  {
    "key":          "XXXX-XXXX-XXXX-XXXX",
    "tier":         "free" | "beta" | "pro" | "lifetime",
    "email":        "user@example.com",
    "validated_at": "2026-03-23T12:00:00",
    "cache_until":  "2026-03-24T12:00:00",
    -- beta-only fields --
    "expires_at":            "2026-04-01T00:00:00Z",  (ISO 8601 UTC)
    "cached_at":             "2026-03-24T00:00:00Z",
    "last_server_contact":   "2026-03-24T00:00:00Z",
    "valid":                 true
  }
"""

from __future__ import annotations
import hashlib
import json
import os
import pathlib
import threading
import datetime
from datetime import timezone
from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.error import URLError
import urllib.request
import urllib.parse
import urllib.error

# ── Gumroad product IDs ──────────────────────────────────────────────────────
_GUMROAD_PRO_ID      = "uriyw"
_GUMROAD_LIFETIME_ID = "tsqtaq"
_GUMROAD_VERIFY_URL  = "https://api.gumroad.com/v2/licenses/verify"

# ── Beta / custom validation server ─────────────────────────────────────────
# URL is fetched dynamically from the config endpoint so no rebuild is needed
# when the server URL changes (e.g. ngrok restart).
_CONFIG_ENDPOINT   = "https://valooptimise.com/api/config.json"
_VALIDATION_URL    = ""   # populated at runtime by _get_validation_url()
_cached_val_url    = ""   # in-memory cache

# ── Cache TTLs ───────────────────────────────────────────────────────────────
_CACHE_HOURS                   = 24       # Gumroad cache (hours)
BETA_CACHE_TTL_SECONDS         = 43_200   # 12 hours
BETA_OFFLINE_HARD_LOCK_SECONDS = 86_400   # 24h without server contact → hard lock

# ── File paths ───────────────────────────────────────────────────────────────
_CFG_DIR  = pathlib.Path.home() / ".valooptimise"
_LIC_FILE = _CFG_DIR / "licence.json"
_DEV_FILE = _CFG_DIR / "dev.key"

# Developer key hash loaded from external file — never hardcoded in source
_DEV_HASH_FILE = _CFG_DIR / "dev_hash.cfg"
_DEV_HASH = ""
try:
    _DEV_HASH = _DEV_HASH_FILE.read_text(encoding="utf-8").strip()
except Exception:
    pass

# ── Emitted when beta licence expires mid-session ────────────────────────────
LICENCE_EXPIRED_EVENT = threading.Event()

# ── Tab definitions ──────────────────────────────────────────────────────────
PRO_TABS = {
    "benchmark",
    "valorant",
    "mousedriver",
    "visual",
    "audio",
    "cpu",
    "gpu",
    "visibility",
    "stats",
}

FREE_TABS = {
    "dashboard",
    "boost",
    "system",
    "network",
    "registry",
    "mouse",
    "startup",
    "guide",
}


# ── Developer bypass ─────────────────────────────────────────────────────────

def _is_dev() -> bool:
    """Returns True if a valid developer key is present locally. Never committed."""
    try:
        key = _DEV_FILE.read_text(encoding="utf-8").strip()
        return hashlib.sha256(key.encode()).hexdigest() == _DEV_HASH
    except Exception:
        return False


# ── Datetime helpers ─────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Naive local time ISO string — used for Gumroad cache fields."""
    return datetime.datetime.now().isoformat()


def _cache_until_iso() -> str:
    return (datetime.datetime.now() + datetime.timedelta(hours=_CACHE_HOURS)).isoformat()


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(timezone.utc)


def _to_iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _from_iso(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(_LIC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _CFG_DIR.mkdir(exist_ok=True)
    tmp = str(_LIC_FILE) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(_LIC_FILE))
    except OSError:
        pass


def _cache_valid(data: dict) -> bool:
    """Gumroad cache validity (existing behaviour, unchanged)."""
    try:
        until = datetime.datetime.fromisoformat(data["cache_until"])
        return datetime.datetime.now() < until
    except Exception:
        return False


def _beta_cache_valid(data: dict) -> bool:
    """
    Beta cache validity: 12h TTL + absolute expiry + 24h offline hard lock.
    Returns False if any check fails.
    """
    if not data.get("valid", True):
        return False

    cached_at_str = data.get("cached_at")
    if not cached_at_str:
        return False

    try:
        cached_at = _from_iso(cached_at_str)
    except (ValueError, TypeError):
        return False

    now = _now_utc()

    # TTL
    if (now - cached_at).total_seconds() > BETA_CACHE_TTL_SECONDS:
        return False

    # Absolute expiry
    expires_str = data.get("expires_at")
    if expires_str:
        try:
            if now > _from_iso(expires_str):
                return False
        except (ValueError, TypeError):
            return False

    # Offline hard lock
    last_contact_str = data.get("last_server_contact")
    if last_contact_str:
        try:
            last_contact = _from_iso(last_contact_str)
            if (now - last_contact).total_seconds() > BETA_OFFLINE_HARD_LOCK_SECONDS:
                return False
        except (ValueError, TypeError):
            pass

    return True


# ── Machine fingerprint ───────────────────────────────────────────────────────

def _get_machine_id() -> str:
    """
    Returns a stable hardware fingerprint using the Windows MachineGuid.
    Falls back to a combination of OS install-specific identifiers that are
    harder to spoof than a hostname.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as k:
            guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            return hashlib.sha256(guid.encode()).hexdigest()[:32]
    except Exception:
        pass
    # Fallback: combine multiple system identifiers for a stronger fingerprint
    import uuid
    parts = []
    try:
        parts.append(str(uuid.getnode()))  # MAC address as int
    except Exception:
        pass
    try:
        parts.append(os.environ.get("COMPUTERNAME", ""))
        parts.append(os.environ.get("PROCESSOR_IDENTIFIER", ""))
    except Exception:
        pass
    if not parts:
        parts.append(os.urandom(16).hex())  # last resort: random, persisted via cache
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


# ── Gumroad validation ────────────────────────────────────────────────────────

def _verify_gumroad(key: str, product_id: str) -> tuple[bool, str]:
    """
    Call Gumroad API to verify a licence key.
    Returns (ok, email_or_error_message).
    """
    try:
        body = urllib.parse.urlencode({
            "product_permalink": product_id,
            "license_key":       key.strip().upper(),
        }).encode()
        req = urllib.request.Request(
            _GUMROAD_VERIFY_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent":   "ValoOptimise/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("success"):
            email = data.get("purchase", {}).get("email", "")
            return True, email
        return False, data.get("message", "Invalid key")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return False, f"HTTP {e.code}: {body}"
    except Exception as ex:
        return False, str(ex)[:200]


# ── Beta key validation ───────────────────────────────────────────────────────

def _get_validation_url() -> str:
    """
    Fetches the current validation server URL from the Cloudflare-hosted config.
    Caches the result in memory. Falls back to the cached value if the fetch fails.
    """
    global _cached_val_url
    try:
        req = urllib.request.Request(_CONFIG_ENDPOINT, method="GET")
        req.add_header("User-Agent", "ValoOptimise/1.0")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            url = data.get("validation_url", "").strip().rstrip("/")
            if url:
                _cached_val_url = url
                return url
    except Exception:
        pass
    return _cached_val_url


def _activate_beta(key: str) -> dict:
    """
    POST key + machine_id to /activate on the validation server.
    Returns {success, tier, expires_at, seconds_remaining, error}.
    error values: "invalid_key", "machine_mismatch", "server_unreachable",
                  "beta_expired", "revoked"
    """
    url = _get_validation_url() + "/activate"
    payload = json.dumps({
        "key":        key.strip(),
        "machine_id": _get_machine_id(),
    }).encode()
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("ngrok-skip-browser-warning", "1")

    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError):
        return {"success": False, "tier": None, "expires_at": None,
                "seconds_remaining": None, "error": "server_unreachable"}
    except Exception:
        return {"success": False, "tier": None, "expires_at": None,
                "seconds_remaining": None, "error": "server_unreachable"}

    if not data.get("activated"):
        return {"success": False, "tier": None, "expires_at": None,
                "seconds_remaining": None, "error": data.get("reason", "invalid_key")}

    # Success — write cache
    now  = _now_utc()
    tier = data.get("tier", "beta")
    entry = {
        "key":                           key.strip(),
        "tier":                          tier,
        "email":                         data.get("email", ""),
        "validated_at":                  _now_iso(),
        "cache_until":                   _cache_until_iso(),
        "valid":                         True,
        "cached_at":                     _to_iso(now),
        "last_server_contact":           _to_iso(now),
    }
    if tier == "beta":
        entry["expires_at"] = data.get("expires_at")
        entry["seconds_remaining_at_cache_time"] = data.get("seconds_remaining", 0)

    _save(entry)
    return {
        "success":           True,
        "tier":              tier,
        "expires_at":        data.get("expires_at"),
        "seconds_remaining": data.get("seconds_remaining"),
        "error":             None,
    }


# ── Beta background check-in ──────────────────────────────────────────────────

_beta_checkin_timer: threading.Timer | None = None
_beta_checkin_lock  = threading.Lock()


def _schedule_beta_checkin(key: str, interval_secs: int = BETA_CACHE_TTL_SECONDS) -> None:
    """Schedules (or reschedules) the 12-hour beta server check-in."""
    global _beta_checkin_timer
    with _beta_checkin_lock:
        if _beta_checkin_timer is not None:
            _beta_checkin_timer.cancel()
        t = threading.Timer(interval_secs, _do_beta_checkin, args=[key])
        t.daemon = True
        t.start()
        _beta_checkin_timer = t


def _do_beta_checkin(key: str) -> None:
    """
    Performs the 12-hour server check-in via GET /beta-status.
    Updates cache; emits LICENCE_EXPIRED_EVENT if beta has ended.
    Reschedules itself on success; retries in 1 hour on network failure.
    """
    key_hash   = hashlib.sha256(key.strip().upper().encode()).hexdigest()
    machine_id = _get_machine_id()
    url = _get_validation_url() + f"/beta-status?h={key_hash}&m={quote(machine_id)}"

    try:
        _req = Request(url, method="GET")
        _req.add_header("ngrok-skip-browser-warning", "1")
        with urlopen(_req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        now   = _now_utc()
        entry = _load()

        if not data.get("valid"):
            # Beta expired or revoked — lock out
            if entry:
                entry["valid"] = False
                _save(entry)
            LICENCE_EXPIRED_EVENT.set()
            return  # Don't reschedule

        # Still valid — refresh timestamps
        if entry:
            entry["cached_at"]             = _to_iso(now)
            entry["last_server_contact"]   = _to_iso(now)
            entry["seconds_remaining_at_cache_time"] = data.get("seconds_remaining", 0)
            _save(entry)

        _schedule_beta_checkin(key)

    except (URLError, OSError):
        # Network failure — retry in 1 hour, don't invalidate cache yet
        _schedule_beta_checkin(key, interval_secs=3_600)


# ── Beta status helpers ───────────────────────────────────────────────────────

def is_beta_expired(data: dict | None = None) -> bool:
    """Returns True if the cached beta licence has passed its expiry timestamp."""
    if data is None:
        data = _load()
    if not data or data.get("tier") != "beta":
        return False
    expires_str = data.get("expires_at")
    if not expires_str:
        return False
    try:
        return _now_utc() > _from_iso(expires_str)
    except (ValueError, TypeError):
        return False


def get_beta_seconds_remaining() -> int:
    """Estimates seconds remaining for the beta licence from the cached expiry. Returns 0 if not beta."""
    data = _load()
    if not data or data.get("tier") != "beta":
        return 0
    expires_str = data.get("expires_at")
    if not expires_str:
        return 0
    try:
        secs = int((_from_iso(expires_str) - _now_utc()).total_seconds())
        return max(0, secs)
    except (ValueError, TypeError):
        return 0


# ── Public API ────────────────────────────────────────────────────────────────

def get_tier() -> str:
    """
    Returns current licence tier: 'free', 'beta', 'pro', or 'lifetime'.
    Developer key (~/.valooptimise/dev.key) grants lifetime silently.
    """
    if _is_dev():
        return "lifetime"
    data = _load()
    if not data.get("key"):
        return "free"

    tier = data.get("tier", "free")

    if tier == "beta":
        if not data.get("valid", True):
            return "free"
        if is_beta_expired(data):
            return "free"
        if not _beta_cache_valid(data):
            return "free"
        return "beta"

    # Gumroad tiers — use cached value (revalidate runs in background on startup)
    if _cache_valid(data):
        return tier
    return tier


def is_pro() -> bool:
    """Returns True for any paid/beta access tier."""
    return get_tier() in ("beta", "pro", "lifetime")


def is_tab_allowed(tab_key: str) -> bool:
    if tab_key in FREE_TABS:
        return True
    return is_pro()


def activate(key: str) -> tuple[bool, str]:
    """
    Attempt to activate a licence key.
    Beta keys (BETA- prefix) go to the validation server only — never Gumroad.
    Pro/Lifetime keys go to Gumroad only.
    Returns (ok, message).
    """
    key = key.strip()
    if not key:
        return False, "Please enter a licence key."

    # ── Beta keys — validation server only ───────────────────────────────────
    if key.upper().startswith("BETA-"):
        result = _activate_beta(key)
        if result["success"]:
            secs = result.get("seconds_remaining") or 0
            days = secs // 86_400
            _schedule_beta_checkin(key)
            return True, f"Beta key activated! {days} day(s) remaining."
        error = result.get("error", "unknown")
        if error == "server_unreachable":
            return False, "Beta server is offline — please try again shortly."
        if error == "beta_expired":
            return False, "This beta key has expired."
        if error == "revoked":
            return False, "This beta key has been revoked."
        if error == "machine_mismatch":
            return False, "This key is already activated on another PC."
        return False, "Invalid beta key."

    # ── Gumroad keys (Pro / Lifetime) ────────────────────────────────────────
    key_upper = key.upper()

    ok, email_or_err = _verify_gumroad(key_upper, _GUMROAD_PRO_ID)
    if ok:
        _save({
            "key":          key_upper,
            "tier":         "pro",
            "email":        email_or_err,
            "validated_at": _now_iso(),
            "cache_until":  _cache_until_iso(),
        })
        return True, f"Pro licence activated! ({email_or_err})"

    ok, email_or_err = _verify_gumroad(key_upper, _GUMROAD_LIFETIME_ID)
    if ok:
        _save({
            "key":          key_upper,
            "tier":         "lifetime",
            "email":        email_or_err,
            "validated_at": _now_iso(),
            "cache_until":  _cache_until_iso(),
        })
        return True, f"Lifetime licence activated! ({email_or_err})"

    return False, "Invalid key — not recognised as a Pro or Lifetime key."


def deactivate() -> None:
    """Remove stored licence key and cancel any beta check-in timer."""
    global _beta_checkin_timer
    with _beta_checkin_lock:
        if _beta_checkin_timer is not None:
            _beta_checkin_timer.cancel()
            _beta_checkin_timer = None
    try:
        _LIC_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def get_info() -> dict:
    """Return dict with key, tier, email, validated_at for display in UI."""
    data = _load()
    info = {
        "tier":         data.get("tier", "free"),
        "email":        data.get("email", ""),
        "key_masked":   _mask_key(data.get("key", "")),
        "validated_at": data.get("validated_at", ""),
    }
    if data.get("tier") == "beta":
        info["beta_expires_at"]        = data.get("expires_at", "")
        info["beta_seconds_remaining"] = get_beta_seconds_remaining()
    return info


def _mask_key(key: str) -> str:
    if len(key) < 8:
        return key
    return key[:4] + "-****-****-" + key[-4:]


def revalidate() -> tuple[bool, str]:
    """
    Force a fresh network validation of the stored key.
    Call this from a background thread on startup.
    """
    data = _load()
    key  = data.get("key", "")
    tier = data.get("tier", "free")
    if not key:
        return True, "free"

    if tier == "beta":
        if is_beta_expired(data) or not data.get("valid", True):
            deactivate()
            LICENCE_EXPIRED_EVENT.set()
            return False, "Beta licence has expired."
        # Trigger an immediate check-in
        _schedule_beta_checkin(key, interval_secs=1)
        return True, "beta"

    product_id = _GUMROAD_PRO_ID if tier == "pro" else _GUMROAD_LIFETIME_ID
    ok, result = _verify_gumroad(key, product_id)
    if ok:
        data["validated_at"] = _now_iso()
        data["cache_until"]  = _cache_until_iso()
        data["email"]        = result
        _save(data)
        return True, tier
    deactivate()
    return False, f"Licence revoked: {result}"


def init_on_startup() -> None:
    """
    Call once at app startup from a background thread.
    Checks for beta expiry and schedules the 12-hour check-in if a beta key
    is present. No-op for free/pro/lifetime tiers.
    """
    data = _load()
    if not data or not data.get("key"):
        return

    tier = data.get("tier", "free")
    if tier != "beta":
        return

    if is_beta_expired(data) or not data.get("valid", True):
        LICENCE_EXPIRED_EVENT.set()
        return

    # Calculate how long until the next check-in is due
    cached_at_str = data.get("cached_at")
    next_checkin  = 0
    if cached_at_str:
        try:
            cached_at    = _from_iso(cached_at_str)
            elapsed      = (_now_utc() - cached_at).total_seconds()
            next_checkin = max(0, int(BETA_CACHE_TTL_SECONDS - elapsed))
        except (ValueError, TypeError):
            next_checkin = 0

    _schedule_beta_checkin(data["key"], interval_secs=next_checkin)
