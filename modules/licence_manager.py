"""
modules/licence_manager.py
===========================
Licence validation for Valo Optimise.
Uses Gumroad's built-in licence key API — no server to maintain.

Tiers
-----
free     — no key required, basic tabs only
pro      — monthly key (Gumroad product)
lifetime — one-time key (Gumroad product)

Storage
-------
~/.valooptimise/licence.json
  {
    "key":          "XXXX-XXXX-XXXX-XXXX",
    "tier":         "pro" | "lifetime",
    "email":        "user@example.com",
    "validated_at": "2026-03-23T12:00:00",
    "cache_until":  "2026-03-24T12:00:00"
  }
"""

from __future__ import annotations
import json
import datetime
import hashlib
import os
import pathlib
import urllib.request
import urllib.parse
import urllib.error

# ── Gumroad product IDs ── (set these after creating products on gumroad.com)
# Each product has a unique permalink — find it in Product > Edit > Permalink
_GUMROAD_PRO_ID      = "valooptimise-pro"       # replace after Gumroad setup
_GUMROAD_LIFETIME_ID = "valooptimise-lifetime"   # replace after Gumroad setup
_GUMROAD_VERIFY_URL  = "https://api.gumroad.com/v2/licenses/verify"

# Cache validation result for 24 hours so we don't hit the API every launch
_CACHE_HOURS = 24

_CFG_DIR  = pathlib.Path.home() / ".valooptimise"
_LIC_FILE = _CFG_DIR / "licence.json"

# ── Pro tabs that require a paid licence ──────────────────────────────────────
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


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        return json.loads(_LIC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _CFG_DIR.mkdir(exist_ok=True)
    _LIC_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()


def _cache_valid(data: dict) -> bool:
    try:
        until = datetime.datetime.fromisoformat(data["cache_until"])
        return datetime.datetime.now() < until
    except Exception:
        return False


def _cache_until_iso() -> str:
    return (datetime.datetime.now() + datetime.timedelta(hours=_CACHE_HOURS)).isoformat()


def _verify_gumroad(key: str, product_id: str) -> tuple[bool, str, str]:
    """
    Call Gumroad API to verify a licence key.
    Returns (ok, tier, email).
    """
    try:
        body = urllib.parse.urlencode({
            "product_permalink": product_id,
            "license_key":       key.strip().upper(),
        }).encode()
        req = urllib.request.Request(
            _GUMROAD_VERIFY_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "ValoOptimise/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("success"):
            purchase = data.get("purchase", {})
            email    = purchase.get("email", "")
            return True, email
        return False, data.get("message", "Invalid key")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return False, f"HTTP {e.code}: {body}"
    except Exception as ex:
        return False, str(ex)[:200]


# ── Public API ────────────────────────────────────────────────────────────────

def get_tier() -> str:
    """
    Returns current licence tier: 'free', 'pro', or 'lifetime'.
    Uses cached result if still valid — no network call needed most launches.
    """
    data = _load()
    if not data.get("key"):
        return "free"
    if _cache_valid(data):
        return data.get("tier", "free")
    # Cache expired — revalidate in background (returns cached tier for now)
    return data.get("tier", "free")


def is_pro() -> bool:
    return get_tier() in ("pro", "lifetime")


def is_tab_allowed(tab_key: str) -> bool:
    if tab_key in FREE_TABS:
        return True
    return is_pro()


def activate(key: str) -> tuple[bool, str]:
    """
    Attempt to activate a licence key.
    Tries Pro product first, then Lifetime.
    Returns (ok, message).
    """
    key = key.strip().upper()
    if not key:
        return False, "Please enter a licence key."

    # Try pro first
    ok, result = _verify_gumroad(key, _GUMROAD_PRO_ID)
    if ok:
        _save({
            "key":          key,
            "tier":         "pro",
            "email":        result,
            "validated_at": _now_iso(),
            "cache_until":  _cache_until_iso(),
        })
        return True, f"Pro licence activated! ({result})"

    # Try lifetime
    ok, result = _verify_gumroad(key, _GUMROAD_LIFETIME_ID)
    if ok:
        _save({
            "key":          key,
            "tier":         "lifetime",
            "email":        result,
            "validated_at": _now_iso(),
            "cache_until":  _cache_until_iso(),
        })
        return True, f"Lifetime licence activated! ({result})"

    return False, f"Invalid key — {result}"


def deactivate() -> None:
    """Remove stored licence key (revert to free tier)."""
    try:
        _LIC_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def get_info() -> dict:
    """Return dict with key, tier, email, validated_at for display in UI."""
    data = _load()
    return {
        "tier":         data.get("tier", "free"),
        "email":        data.get("email", ""),
        "key_masked":   _mask_key(data.get("key", "")),
        "validated_at": data.get("validated_at", ""),
    }


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

    product_id = _GUMROAD_PRO_ID if tier == "pro" else _GUMROAD_LIFETIME_ID
    ok, result = _verify_gumroad(key, product_id)
    if ok:
        data["validated_at"] = _now_iso()
        data["cache_until"]  = _cache_until_iso()
        data["email"]        = result
        _save(data)
        return True, tier
    else:
        # Key invalid/revoked — downgrade to free
        deactivate()
        return False, f"Licence revoked: {result}"
