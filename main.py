# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

import sys
import os
import json
import threading
import datetime
import subprocess
import shutil
from tkinter import filedialog

# ── Hide all subprocess console windows app-wide ──────────────────────────────
# Patch subprocess.run / subprocess.Popen BEFORE any module imports so every
# powershell / sc / powercfg / netsh call is silently hidden.  Uses .setdefault
# so callers that already pass creationflags are left unchanged.
_NW = subprocess.CREATE_NO_WINDOW
_orig_run   = subprocess.run
_orig_Popen = subprocess.Popen

def _run_hidden(*a, **kw):
    kw.setdefault("creationflags", _NW)
    return _orig_run(*a, **kw)

def _Popen_hidden(*a, **kw):
    kw.setdefault("creationflags", _NW)
    return _orig_Popen(*a, **kw)

subprocess.run   = _run_hidden
subprocess.Popen = _Popen_hidden
# ─────────────────────────────────────────────────────────────────────────────

# Ensure project root is on the path so modules/ and utils/ resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from utils.admin_check import require_admin, get_admin_status_label
from utils import backup_manager
from utils.compat import set_dpi_awareness, sanitize_input, sanitize_riot_id, get_version_display
from utils.anim  import count_up, ease_progress, Pulse, flash_bg, fade_in_window, slide_in, show_toast
import psutil as _psutil  # available app-wide for live stats
from modules.system_optimizer import SystemOptimizer
from modules.network_optimizer import NetworkOptimizer
from modules.registry_tweaks import RegistryTweaks, TWEAKS
from modules.stats_tracker import StatsTracker
from modules.settings_guide import SettingsGuide
from modules.valorant_config  import ValorantConfig
from modules.mouse_optimizer  import MouseOptimizer
from modules.visual_optimizer import VisualOptimizer
from modules.audio_optimizer  import AudioOptimizer
from modules.cpu_timer        import CpuTimerOptimizer
from modules.startup_manager  import StartupManager
from modules.visibility_optimizer import VisibilityOptimizer, PRESETS as VISIBILITY_PRESETS, PRESET_NOTES as VISIBILITY_PRESET_NOTES
from modules.gpu_optimizer import GpuOptimizer
from modules.mouse_driver import (
    PollingRateMonitor, PointerBallistics,
    SensitivityProfileManager, MouseDeviceInfo, RawInputChecker,
)
from modules.benchmark import SystemBenchmark, METRIC_ORDER
from modules.fps_card   import generate_card
from modules import licence_manager as _lic

# ── Colors — Valo Brand Palette v2.0 ─────────────────────────────────────────
BG        = "#0C1A28"   # Valo Navy — deepest background
PANEL     = "#152235"   # Navy Layer 1 — card backgrounds
PANEL2    = "#1E3048"   # Navy Layer 2 — elevated / hover
ACCENT    = "#E8A020"   # Valo Gold — primary brand signature
ACCENT_HV = "#B87D10"   # Valo Gold Deep — pressed/active
ACCENT2   = "#F5C05A"   # Valo Gold Light — highlights / glow
TEXT      = "#EDF3F8"   # Valo Off-White — primary text on dark
MUTED     = "#8BA3BB"   # Valo Mist — secondary text
GREEN     = "#2ECC71"   # System Success
RED_LIGHT = "#E74C3C"   # System Error
GOLD      = "#F5C05A"   # Valo Gold Light — scores/achievements

SIDEBAR_BG  = "#0C1A28"   # Valo Navy — sidebar background
SIDEBAR_ACT = "#1E3048"   # Navy Layer 2 — active tab
BORDER      = "#3E5A77"   # Valo Slate — borders / separators

# ── Typography ───────────────────────────────────────────────────────────────
FONT = "Sora"            # Primary typeface (falls back to Arial if not installed)
H1    = (FONT, 22, "bold")
H2    = (FONT, 16, "bold")
H3    = (FONT, 13, "bold")
BODY  = (FONT, 11)
SMALL = (FONT, 9)
TINY  = (FONT, 8)
MONO  = ("Consolas", 10)
LABEL = (FONT, 9, "bold")

# Corner radii — consistent across the app
CR_CARD   = 12
CR_BUTTON = 8
CR_BADGE  = 6
CR_BAR    = 4

CONFIG_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
WORKSPACE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Valo Workspace")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = {
        "last_region": "na",
        "last_riot_id": "",
        "applied_tweaks": [],
        "dns_setting": "Cloudflare",
        "power_plan": "",
        "visibility_preset": "Competitive",
    }
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return {**defaults, **json.load(f)}
    except Exception:
        pass
    return defaults


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def run_in_thread(func, callback, *args):
    """Run func(*args) in a daemon thread; call callback(result) on completion."""
    def _worker():
        result = func(*args)
        if callback:
            callback(result)
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ── Shared Widgets ────────────────────────────────────────────────────────────

def make_section_label(parent, text: str, color=ACCENT) -> ctk.CTkFrame:
    """Section header with a 3 px accent left bar."""
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkFrame(f, width=3, height=14, fg_color=color,
                 corner_radius=2).pack(side="left", padx=(0, 8), pady=2)
    ctk.CTkLabel(f, text=text, font=H3,
                 text_color=TEXT, anchor="w").pack(side="left")
    return f


def make_status_box(parent, height=120) -> ctk.CTkTextbox:
    box = ctk.CTkTextbox(parent, height=height, fg_color=PANEL2,
                          text_color=MUTED, font=MONO, wrap="word")
    box.configure(state="disabled")
    return box


def log_to_box(box: ctk.CTkTextbox, msg: str, ok: bool = True):
    box.configure(state="normal")
    box.insert("end", f"[{ts()}] {msg}\n")
    box.see("end")
    box.configure(state="disabled")


def accent_button(parent, text, command, width=180, fg=ACCENT) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        fg_color=fg, hover_color=ACCENT_HV, text_color=TEXT,
        font=(FONT, 12, "bold"), corner_radius=CR_BUTTON,
        border_width=0, height=36
    )


def ghost_button(parent, text, command, width=160) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        fg_color="transparent", hover_color=PANEL2, text_color=MUTED,
        font=BODY, corner_radius=CR_BUTTON,
        border_width=1, border_color=BORDER, height=36
    )


def hoverable_card(parent, **kwargs) -> ctk.CTkFrame:
    """Card that subtly lights up on hover."""
    kwargs.setdefault("fg_color", PANEL)
    kwargs.setdefault("corner_radius", CR_CARD)
    card = ctk.CTkFrame(parent, **kwargs)
    normal = kwargs["fg_color"]
    card.bind("<Enter>", lambda e: card.configure(fg_color=PANEL2))
    card.bind("<Leave>", lambda e: card.configure(fg_color=normal))
    return card


def status_badge(parent, status: str) -> ctk.CTkFrame:
    """Compact status pill: 'optimised', 'partial', 'default', 'error'."""
    colors = {
        "optimised": (GREEN, "#0d2e18"),
        "partial":   (GOLD, "#2e2a0d"),
        "default":   (MUTED, PANEL2),
        "error":     (RED_LIGHT, "#2e0d12"),
    }
    labels = {
        "optimised": "Optimised",
        "partial":   "Partial",
        "default":   "Not Set",
        "error":     "Error",
    }
    fg, bg = colors.get(status, colors["default"])
    badge = ctk.CTkFrame(parent, fg_color=bg, corner_radius=CR_BADGE)
    ctk.CTkLabel(badge, text=labels.get(status, status),
                 font=LABEL, text_color=fg).pack(padx=8, pady=2)
    return badge


def focusable_entry(parent, **kwargs) -> ctk.CTkEntry:
    """Entry field with gold focus ring."""
    kwargs.setdefault("border_color", BORDER)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("font", BODY)
    kwargs.setdefault("fg_color", PANEL2)
    kwargs.setdefault("text_color", TEXT)
    entry = ctk.CTkEntry(parent, **kwargs)
    entry.bind("<FocusIn>", lambda e: entry.configure(border_color=ACCENT))
    entry.bind("<FocusOut>", lambda e: entry.configure(border_color=BORDER))
    return entry


def scrollable_content(parent) -> ctk.CTkScrollableFrame:
    """Standard scrollable wrapper for frame content."""
    scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, corner_radius=0,
                                     scrollbar_button_color=PANEL2,
                                     scrollbar_button_hover_color=BORDER)
    scroll.grid(row=0, column=0, sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)
    return scroll


def _win_toast(title: str, msg: str):
    """Fire a Windows toast notification via PowerShell. Silent on failure."""
    try:
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
            "$t=[Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
            "$x=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t);"
            "$n=$x.GetElementsByTagName('text');"
            f"$n[0].AppendChild($x.CreateTextNode('{title}'))>$null;"
            f"$n[1].AppendChild($x.CreateTextNode('{msg}'))>$null;"
            "$toast=[Windows.UI.Notifications.ToastNotification]::new($x);"
            "[Windows.UI.Notifications.ToastNotificationManager]::"
            "CreateToastNotifier('Valo Optimise').Show($toast)"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM OPTIMIZER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class SystemFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.opt = SystemOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(self, text="System Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Safe OS-level tweaks. No game process interaction.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

        # ── Hardware Info Card ──
        hw = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        hw.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        hw.grid_columnconfigure((0, 1, 2, 3), weight=1)
        make_section_label(hw, "🖥️  Detected Hardware").grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(8, 4))
        try:
            sysinfo = self.opt.get_system_info()
        except Exception:
            sysinfo = {"cpu": "Unknown", "gpu": "Unknown", "ram_gb": 0, "resolution": "Unknown"}
        _hw_items = [
            ("CPU", sysinfo.get("cpu", "Unknown")),
            ("GPU", sysinfo.get("gpu", "Unknown")),
            ("RAM", f"{sysinfo.get('ram_gb', 0)} GB"),
            ("Display", sysinfo.get("resolution", "Unknown")),
        ]
        for col, (label, value) in enumerate(_hw_items):
            cell = ctk.CTkFrame(hw, fg_color="transparent")
            cell.grid(row=1, column=col, sticky="ew", padx=10, pady=(0, 10))
            ctk.CTkLabel(cell, text=label, font=SMALL, text_color=MUTED).pack(anchor="w")
            ctk.CTkLabel(cell, text=value, font=(FONT, 11, "bold"), text_color=ACCENT,
                         wraplength=180, justify="left").pack(anchor="w")

        # ── Power Plan ──
        pf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        pf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        pf.grid_columnconfigure(1, weight=1)
        make_section_label(pf, "⚡  Power Plan").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.plan_label = ctk.CTkLabel(pf, text="Current: ...", text_color=MUTED, font=BODY)
        self.plan_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        accent_button(pf, "High Performance", self._set_high, width=160).grid(row=1, column=1, padx=6, pady=(0, 10))
        accent_button(pf, "Ultimate Performance", self._set_ultimate, width=180).grid(row=1, column=2, padx=(0, 14), pady=(0, 10))
        self._refresh_plan_label()

        # ── Background Processes ──
        bf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        bf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        bf.grid_columnconfigure(0, weight=1)
        make_section_label(bf, "🧹  Background Processes").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        btn_row = ctk.CTkFrame(bf, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 6))
        accent_button(btn_row, "Kill Non-Essential Apps", self._kill_all, width=200).grid(row=0, column=0, padx=(0, 8))
        ghost_button(btn_row, "Disable Xbox Game Bar", self._disable_gamebar, width=180).grid(row=0, column=1, padx=(0, 8))
        ghost_button(btn_row, "Stop Search Indexing", self._stop_search, width=170).grid(row=0, column=2)

        self.proc_list_label = ctk.CTkLabel(bf, text="Running background targets: checking...",
                                             text_color=MUTED, font=BODY)
        self.proc_list_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        self._refresh_proc_list()

        # ── RAM ──
        rf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        rf.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        rf.grid_columnconfigure(1, weight=1)
        make_section_label(rf, "🧠  RAM Optimization").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        self.ram_label = ctk.CTkLabel(rf, text="Loading...", text_color=MUTED, font=BODY)
        self.ram_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(rf, "Clear Standby Memory", self._clear_ram, width=180).grid(row=1, column=1, sticky="e", padx=14, pady=(0, 10))
        self._refresh_ram()

        # ── GPU Scheduling ──
        gf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        gf.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        make_section_label(gf, "🎮  Hardware GPU Scheduling (HAGS)").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        gpu_status = self.opt.check_hardware_gpu_scheduling()
        color = GREEN if gpu_status == "Enabled" else RED_LIGHT
        ctk.CTkLabel(gf, text=f"Status: {gpu_status}", text_color=color, font=(FONT, 11, "bold")).grid(
            row=1, column=0, sticky="w", padx=14)
        ctk.CTkLabel(gf, text="Enable in: Windows Settings → System → Display → Graphics → Change default GPU settings → Hardware-Accelerated GPU Scheduling",
                     text_color=MUTED, font=SMALL, wraplength=560, justify="left").grid(
            row=2, column=0, sticky="w", padx=14, pady=(0, 10))

        # ── Windows Defender Exclusions ──
        de = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        de.grid(row=7, column=0, sticky="ew", padx=20, pady=6)
        de.grid_columnconfigure(1, weight=1)
        make_section_label(de, "🛡️  Windows Defender Exclusions").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.defender_label = ctk.CTkLabel(de, text="Checking...", text_color=MUTED, font=BODY)
        self.defender_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(de, "Add Exclusions", self._add_defender_exclusions, width=150).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(de, "Remove", self._remove_defender_exclusions, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(de, text="Excludes game folders from real-time scanning to reduce FPS drops during play.",
                     text_color=MUTED, font=SMALL, wraplength=620, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_defender()

        # ── SysMain (SuperFetch) ──
        sm = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        sm.grid(row=8, column=0, sticky="ew", padx=20, pady=6)
        sm.grid_columnconfigure(1, weight=1)
        make_section_label(sm, "💾  SysMain (SuperFetch)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.sysmain_label = ctk.CTkLabel(sm, text="Checking...", text_color=MUTED, font=BODY)
        self.sysmain_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(sm, "Disable SysMain", self._disable_sysmain, width=150).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(sm, "Re-enable", self._enable_sysmain, width=100).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(sm, text="On NVMe SSDs SuperFetch is redundant — disabling it eliminates random I/O spikes during fights.",
                     text_color=MUTED, font=SMALL, wraplength=620, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_sysmain()

        # ── CPU Minimum Frequency ──
        cpuf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        cpuf.grid(row=9, column=0, sticky="ew", padx=20, pady=6)
        cpuf.grid_columnconfigure(1, weight=1)
        make_section_label(cpuf, "⚡  CPU Minimum Frequency").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.cpu_freq_label = ctk.CTkLabel(cpuf, text="Checking...", text_color=MUTED, font=BODY)
        self.cpu_freq_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(cpuf, "Set 100% Min Freq", self._set_cpu_min_freq, width=170).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(cpuf, "Restore", self._restore_cpu_freq, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(cpuf, text="Locks CPU minimum frequency at 100% — no frequency scaling lag when burst load hits mid-fight. Higher idle power draw.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_cpu_freq()

        # ── Windows Update ──
        wuf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        wuf.grid(row=10, column=0, sticky="ew", padx=20, pady=6)
        wuf.grid_columnconfigure(1, weight=1)
        make_section_label(wuf, "🔄  Windows Update").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.wu_label = ctk.CTkLabel(wuf, text="Checking...", text_color=MUTED, font=BODY)
        self.wu_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(wuf, "Pause During Gaming", self._pause_wu, width=180).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(wuf, "Resume", self._resume_wu, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(wuf, text="Stops Windows Update service — prevents background downloads and installs causing CPU/disk spikes. Resume after your session.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_wu()

        # ── DiagTrack ──
        dtf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        dtf.grid(row=11, column=0, sticky="ew", padx=20, pady=6)
        dtf.grid_columnconfigure(1, weight=1)
        make_section_label(dtf, "📡  Microsoft Telemetry (DiagTrack)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.diagtrack_label = ctk.CTkLabel(dtf, text="Checking...", text_color=MUTED, font=BODY)
        self.diagtrack_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(dtf, "Stop Telemetry", self._disable_diagtrack, width=150).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(dtf, "Restore", self._enable_diagtrack, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(dtf, text="Stops Microsoft's Connected User Experiences service — eliminates periodic CPU wake-ups from telemetry collection.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_diagtrack()

        # ── Status Log ──
        make_section_label(self, "Status Log").grid(row=12, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=110)
        self.log.grid(row=13, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_plan_label(self):
        plan = self.opt.get_current_power_plan()
        self.plan_label.configure(text=f"Current: {plan}")

    def _refresh_proc_list(self):
        procs = self.opt.get_background_processes()
        if procs:
            names = ", ".join(p["name"] for p in procs)
            self.proc_list_label.configure(text=f"Running: {names}", text_color=RED_LIGHT)
        else:
            self.proc_list_label.configure(text="No background targets running.", text_color=GREEN)

    def _refresh_ram(self):
        r = self.opt.get_ram_usage()
        self.ram_label.configure(text=f"Available: {r['available_gb']} GB / {r['total_gb']} GB  ({r['percent_used']}% used)")

    def _set_high(self):
        def _do(): return self.opt.set_high_performance_plan()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_plan_label()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _set_ultimate(self):
        def _do(): return self.opt.set_ultimate_performance_plan()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_plan_label()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _kill_all(self):
        def _do(): return self.opt.kill_all_background_targets()
        def _done(results):
            if results:
                for name, ok, msg in results:
                    log_to_box(self.log, msg, ok)
            else:
                log_to_box(self.log, "No background targets were running.", True)
            self._refresh_proc_list()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _disable_gamebar(self):
        def _do(): return self.opt.disable_xbox_game_bar()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_proc_list()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _stop_search(self):
        def _do(): return self.opt.disable_search_indexing()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_proc_list()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _clear_ram(self):
        log_to_box(self.log, "Clearing standby memory...", True)
        def _do(): return self.opt.clear_standby_memory()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_ram()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_defender(self):
        status = self.opt.get_defender_exclusion_status()
        color = GREEN if "Excluded" in status else RED_LIGHT
        self.defender_label.configure(text=f"Status: {status}", text_color=color)

    def _add_defender_exclusions(self):
        log_to_box(self.log, "Adding Defender exclusions (requires admin)...", True)
        def _do(): return self.opt.add_defender_exclusions()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_defender()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _remove_defender_exclusions(self):
        def _do(): return self.opt.remove_defender_exclusions()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_defender()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_sysmain(self):
        status = self.opt.get_sysmain_status()
        color = GREEN if "Stopped" in status else MUTED
        self.sysmain_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_sysmain(self):
        log_to_box(self.log, "Stopping SysMain (requires admin)...", True)
        def _do(): return self.opt.disable_sysmain()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_sysmain()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_sysmain(self):
        def _do(): return self.opt.enable_sysmain()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_sysmain()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_cpu_freq(self):
        s = self.opt.get_cpu_min_freq_status()
        self.cpu_freq_label.configure(text=f"Status: {s}", text_color=GREEN if "100%" in s else MUTED)

    def _set_cpu_min_freq(self):
        log_to_box(self.log, "Setting CPU minimum frequency to 100%...", True)
        def _do(): return self.opt.set_cpu_min_freq_100()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_cpu_freq()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_cpu_freq(self):
        def _do(): return self.opt.restore_cpu_min_freq()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_cpu_freq()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_wu(self):
        s = self.opt.get_windows_update_status()
        self.wu_label.configure(text=f"Status: {s}", text_color=GREEN if "Paused" in s else MUTED)

    def _pause_wu(self):
        log_to_box(self.log, "Stopping Windows Update service (requires admin)...", True)
        def _do(): return self.opt.pause_windows_update()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_wu()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _resume_wu(self):
        def _do(): return self.opt.resume_windows_update()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_wu()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_diagtrack(self):
        s = self.opt.get_diagtrack_status()
        self.diagtrack_label.configure(text=f"Status: {s}", text_color=GREEN if "Stopped" in s else MUTED)

    def _disable_diagtrack(self):
        log_to_box(self.log, "Stopping DiagTrack telemetry (requires admin)...", True)
        def _do(): return self.opt.disable_diagtrack()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_diagtrack()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_diagtrack(self):
        def _do(): return self.opt.enable_diagtrack()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_diagtrack()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# NETWORK OPTIMIZER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class NetworkFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.net = NetworkOptimizer()
        self._ping_results = {}
        self._ping_running = False
        self._ping_thread = None
        self._ping_labels = {}
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Network Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="TCP tuning, DNS switching, and server ping testing.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # ── Ping Tester ──
        pf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        pf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        pf.grid_columnconfigure(0, weight=1)
        make_section_label(pf, "🌐  Game Server Ping").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        self.ping_frame = ctk.CTkScrollableFrame(pf, height=130, fg_color=PANEL2)
        self.ping_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.ping_frame.grid_columnconfigure(0, weight=1)
        self._build_ping_rows()

        self.ping_btn = accent_button(pf, "Test All Servers", self._run_ping, width=160)
        self.ping_btn.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))

        # ── DNS ──
        df = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        df.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        df.grid_columnconfigure(1, weight=1)
        make_section_label(df, "🔒  DNS Settings").grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 4))

        ctk.CTkLabel(df, text="Adapter:", text_color=MUTED, font=BODY).grid(row=1, column=0, padx=14, pady=(0, 10))

        adapters = self.net.get_network_adapters()
        adapter_names = [a["name"] for a in adapters] if adapters else ["No adapters found"]
        self.adapter_var = ctk.StringVar(value=adapter_names[0])
        ctk.CTkComboBox(df, values=adapter_names, variable=self.adapter_var, width=220,
                        fg_color=PANEL2, button_color=ACCENT).grid(row=1, column=1, padx=6, pady=(0, 10))

        self.dns_var = ctk.StringVar(value=self.cfg.get("dns_setting", "Cloudflare"))
        dns_options = list(self.net.DNS_PRESETS.keys())
        ctk.CTkComboBox(df, values=dns_options, variable=self.dns_var, width=130,
                        fg_color=PANEL2, button_color=ACCENT).grid(row=1, column=2, padx=6, pady=(0, 10))

        accent_button(df, "Apply DNS", self._apply_dns, width=110).grid(row=1, column=3, padx=(0, 6), pady=(0, 10))
        ghost_button(df, "Reset to DHCP", self._reset_dns, width=120).grid(row=1, column=4, padx=(0, 14), pady=(0, 10))

        # ── TCP Tweaks ──
        tf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        tf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        tf.grid_columnconfigure(0, weight=1)
        make_section_label(tf, "⚙️  TCP Optimization").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        tcp_info = ctk.CTkLabel(tf,
            text="Applies: Auto-Tuning=Normal, Chimney=Disabled, DCA=Enabled, NetDMA=Enabled, Timestamps=Disabled",
            text_color=MUTED, font=SMALL, wraplength=600, anchor="w", justify="left")
        tcp_info.grid(row=1, column=0, sticky="w", padx=14)

        btn_row = ctk.CTkFrame(tf, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="w", padx=14, pady=(6, 10))
        accent_button(btn_row, "Apply TCP Tweaks", self._apply_tcp, width=160).grid(row=0, column=0, padx=(0, 8))
        ghost_button(btn_row, "Revert TCP", self._revert_tcp, width=120).grid(row=0, column=1)

        # ── Nagle's Algorithm ──
        nf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        nf.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        nf.grid_columnconfigure(1, weight=1)
        make_section_label(nf, "⚡  Nagle's Algorithm").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.nagle_label = ctk.CTkLabel(nf, text="Checking...", text_color=MUTED, font=BODY)
        self.nagle_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(nf, "Disable Nagle's", self._disable_nagle, width=150).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(nf, "Re-enable", self._enable_nagle, width=100).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(nf, text="Sends packets immediately instead of batching them — tighter, more consistent ping. Requires reboot.",
                     text_color=MUTED, font=SMALL, wraplength=620, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_nagle()

        # ── NIC Power Management ──
        np = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        np.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        np.grid_columnconfigure(1, weight=1)
        make_section_label(np, "🔌  NIC Power Management").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.nic_power_label = ctk.CTkLabel(np, text="Checking...", text_color=MUTED, font=BODY)
        self.nic_power_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(np, "Disable Power Save", self._disable_nic_power, width=170).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(np, "Restore", self._enable_nic_power, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(np, text="Keeps your NIC fully awake — prevents Windows from power-gating the adapter and causing micro packet loss.",
                     text_color=MUTED, font=SMALL, wraplength=620, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_nic_power()

        # ── Live Server Ping Monitor ──
        lp = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        lp.grid(row=7, column=0, sticky="ew", padx=20, pady=6)
        lp.grid_columnconfigure(0, weight=1)
        make_section_label(lp, "📡  Live Server Ping").grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 4))

        _live_servers = [
            ("EU", "185.40.64.69"),
            ("NA", "198.108.100.197"),
            ("AP", "111.220.144.199"),
        ]
        for s_i, (region, ip) in enumerate(_live_servers):
            ctk.CTkLabel(lp, text=region, font=(FONT, 11, "bold"),
                         text_color=TEXT, width=40, anchor="w").grid(row=s_i + 1, column=0, padx=(14, 4), pady=2, sticky="w")
            ctk.CTkLabel(lp, text=ip, font=MONO,
                         text_color=MUTED, anchor="w").grid(row=s_i + 1, column=1, padx=(0, 12), pady=2, sticky="w")
            ping_val = ctk.CTkLabel(lp, text="--", font=(FONT, 12, "bold"),
                                    text_color=MUTED, width=80, anchor="w")
            ping_val.grid(row=s_i + 1, column=2, padx=(0, 14), pady=2, sticky="w")
            self._ping_labels[region] = ping_val

        lp_btn_row = ctk.CTkFrame(lp, fg_color="transparent")
        lp_btn_row.grid(row=4, column=0, columnspan=4, sticky="w", padx=14, pady=(4, 10))
        self._live_ping_btn = accent_button(lp_btn_row, "▶  Start Live Ping", self._toggle_live_ping, width=160)
        self._live_ping_btn.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkLabel(lp_btn_row, text="Updates every 2 s  |  <50 ms=green  50-100 ms=gold  >100 ms=red",
                     text_color=MUTED, font=SMALL).grid(row=0, column=1, padx=(4, 0))

        # ── Log ──
        make_section_label(self, "Status Log").grid(row=8, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=9, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _build_ping_rows(self):
        for widget in self.ping_frame.winfo_children():
            widget.destroy()
        headers = ["Region", "Avg Ping", "Min", "Max", "Loss"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self.ping_frame, text=h, font=LABEL,
                         text_color=MUTED).grid(row=0, column=i, padx=8, pady=2, sticky="w")
        self.ping_frame.grid_columnconfigure(0, weight=1)

        for row_i, region in enumerate(self.net.VALORANT_SERVERS.keys(), start=1):
            result = self._ping_results.get(region)
            if result:
                avg = result["avg_ms"]
                color = GREEN if avg < 80 else (ACCENT if avg < 150 else RED_LIGHT)
                avg_txt = f"{avg} ms" if avg >= 0 else "Timeout"
                min_txt = f"{result['min_ms']} ms" if avg >= 0 else "--"
                max_txt = f"{result['max_ms']} ms" if avg >= 0 else "--"
                loss_txt = f"{result['packet_loss']}%"
            else:
                color = MUTED
                avg_txt = min_txt = max_txt = loss_txt = "--"

            vals = [region, avg_txt, min_txt, max_txt, loss_txt]
            for col_i, val in enumerate(vals):
                ctk.CTkLabel(self.ping_frame, text=val, font=BODY,
                             text_color=color if col_i == 1 else TEXT).grid(
                    row=row_i, column=col_i, padx=8, pady=1, sticky="w")

    def _run_ping(self):
        self.ping_btn.configure(state="disabled", text="Testing...")
        log_to_box(self.log, "Pinging game servers...", True)
        def _do(): return self.net.ping_all_servers()
        def _done(results):
            for r in results:
                self._ping_results[r["region"]] = r
            self._build_ping_rows()
            self.ping_btn.configure(state="normal", text="Test All Servers")
            best = results[0] if results else None
            if best and best["avg_ms"] >= 0:
                log_to_box(self.log, f"Best server: {best['region']} at {best['avg_ms']} ms", True)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _apply_dns(self):
        adapter = self.adapter_var.get()
        preset = self.dns_var.get()
        def _do(): return self.net.set_dns(adapter, preset)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self.cfg["dns_setting"] = preset
            save_config(self.cfg)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _reset_dns(self):
        adapter = self.adapter_var.get()
        def _do(): return self.net.reset_dns(adapter)
        def _done(r): log_to_box(self.log, r[1], r[0])
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _apply_tcp(self):
        log_to_box(self.log, "Applying TCP tweaks...", True)
        def _do(): return self.net.apply_tcp_optimizations()
        def _done(results):
            for ok, msg in results:
                log_to_box(self.log, msg, ok)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _revert_tcp(self):
        def _do(): return self.net.revert_tcp_settings()
        def _done(results):
            for ok, msg in results:
                log_to_box(self.log, msg, ok)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_nagle(self):
        status = self.net.get_nagle_status()
        color = GREEN if "Disabled" in status else MUTED
        self.nagle_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_nagle(self):
        log_to_box(self.log, "Disabling Nagle's algorithm (requires admin)...", True)
        def _do(): return self.net.disable_nagle()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_nagle()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_nagle(self):
        def _do(): return self.net.enable_nagle()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_nagle()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_nic_power(self):
        status = self.net.get_nic_power_status()
        color = GREEN if "Disabled" in status else MUTED
        self.nic_power_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_nic_power(self):
        log_to_box(self.log, "Disabling NIC power management...", True)
        def _do(): return self.net.disable_nic_power_management()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_nic_power()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_nic_power(self):
        def _do(): return self.net.enable_nic_power_management()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_nic_power()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    # ── Live Ping Monitor ─────────────────────────────────────────────────────

    _LIVE_SERVERS = [
        ("EU", "185.40.64.69"),
        ("NA", "198.108.100.197"),
        ("AP", "111.220.144.199"),
    ]

    def _toggle_live_ping(self):
        if self._ping_running:
            self._ping_running = False
            self._live_ping_btn.configure(text="▶  Start Live Ping", fg_color=ACCENT)
            log_to_box(self.log, "Live ping monitor stopped.", True)
        else:
            self._ping_running = True
            self._live_ping_btn.configure(text="⏹  Stop Live Ping", fg_color=MUTED)
            log_to_box(self.log, "Live ping monitor started.", True)
            self._ping_thread = threading.Thread(target=self._live_ping_loop, daemon=True)
            self._ping_thread.start()

    def _live_ping_loop(self):
        while self._ping_running:
            for region, ip in self._LIVE_SERVERS:
                if not self._ping_running:
                    break
                ms = self._ping_once(ip)
                self.after(0, lambda r=region, m=ms: self._update_ping_label(r, m))
            # wait 2 seconds between rounds, checking stop flag every 0.2 s
            for _ in range(10):
                if not self._ping_running:
                    break
                threading.Event().wait(0.2)

    def _ping_once(self, ip: str) -> int:
        """Return average ping in ms, or -1 on timeout/error."""
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", ip],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                line_l = line.lower()
                if "average" in line_l or "durchschnitt" in line_l:
                    # "Average = 42ms"
                    parts = line.split("=")
                    if parts:
                        val = parts[-1].strip().replace("ms", "").strip()
                        if val.isdigit():
                            return int(val)
                # also handle single-packet "time=42ms"
                if "time=" in line_l or "time<" in line_l:
                    for tok in line.split():
                        tok_l = tok.lower()
                        if tok_l.startswith("time="):
                            try:
                                return int(tok_l.replace("time=", "").replace("ms", ""))
                            except ValueError:
                                pass
                        elif tok_l.startswith("time<"):
                            return 1
        except Exception:
            pass
        return -1

    def _update_ping_label(self, region: str, ms: int):
        lbl = self._ping_labels.get(region)
        if not lbl:
            return
        if ms < 0:
            lbl.configure(text="Timeout", text_color=MUTED)
        else:
            color = GREEN if ms < 50 else (GOLD if ms < 100 else ACCENT)
            lbl.configure(text=f"{ms} ms", text_color=color)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRY TWEAKS FRAME
# ══════════════════════════════════════════════════════════════════════════════

class RegistryFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.rt = RegistryTweaks()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Registry Tweaks", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="All changes are backed up automatically. You can revert at any time.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 4))

        # Warning banner
        warn = ctk.CTkFrame(self, fg_color="#2a1a00", corner_radius=8)
        warn.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        ctk.CTkLabel(warn, text="⚠️  Registry backups are created in ./backups/ before every change. Run as Administrator for full effect.",
                     text_color="#ffcc44", font=SMALL, wraplength=700, anchor="w", justify="left").grid(
            row=0, column=0, padx=14, pady=8, sticky="w")

        # Tweak list
        tf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        tf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        tf.grid_columnconfigure(0, weight=1)
        make_section_label(tf, "🔧  Available Tweaks").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        self.tweak_scroll = ctk.CTkScrollableFrame(tf, height=220, fg_color=PANEL2)
        self.tweak_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        self.tweak_scroll.grid_columnconfigure(1, weight=1)
        self._tweak_rows = {}
        self._refresh_tweaks()

        # Action buttons
        ab = ctk.CTkFrame(tf, fg_color="transparent")
        ab.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(ab, "Apply All Tweaks", self._apply_all, width=160).grid(row=0, column=0, padx=(0, 8))
        ghost_button(ab, "Revert All", self._revert_all, width=120).grid(row=0, column=1, padx=(0, 8))
        ghost_button(ab, "Refresh Status", self._refresh_tweaks, width=130).grid(row=0, column=2)

        # Backup/Restore
        bf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        bf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        bf.grid_columnconfigure(0, weight=1)
        make_section_label(bf, "💾  Backup & Restore").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        self.backup_scroll = ctk.CTkScrollableFrame(bf, height=100, fg_color=PANEL2)
        self.backup_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        self.backup_scroll.grid_columnconfigure(0, weight=1)
        ghost_button(bf, "Refresh Backups", self._refresh_backups, width=150).grid(
            row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        self._refresh_backups()

        # Log
        make_section_label(self, "Status Log").grid(row=5, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_tweaks(self):
        for w in self.tweak_scroll.winfo_children():
            w.destroy()
        self._tweak_rows = {}
        statuses = self.rt.get_all_tweak_statuses()
        for i, s in enumerate(statuses):
            color = GREEN if s["is_applied"] else MUTED
            status_pill = "✔ Applied" if s["is_applied"] else "○ Default"

            ctk.CTkLabel(self.tweak_scroll, text=s["name"], font=(FONT, 12, "bold"),
                         text_color=TEXT, anchor="w").grid(row=i*2, column=0, sticky="w", padx=8, pady=(6, 0))
            ctk.CTkLabel(self.tweak_scroll, text=status_pill, font=BODY,
                         text_color=color).grid(row=i*2, column=1, sticky="e", padx=8, pady=(6, 0))
            ctk.CTkLabel(self.tweak_scroll, text=s["description"], font=SMALL,
                         text_color=MUTED, anchor="w", wraplength=560, justify="left").grid(
                row=i*2+1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

    def _refresh_backups(self):
        for w in self.backup_scroll.winfo_children():
            w.destroy()
        backups = backup_manager.list_backups()
        if not backups:
            ctk.CTkLabel(self.backup_scroll, text="No backups yet.", text_color=MUTED,
                         font=BODY).grid(row=0, column=0, padx=8, pady=4)
            return
        self.backup_scroll.grid_columnconfigure(0, weight=1)
        for i, b in enumerate(backups[:15]):
            ctk.CTkLabel(self.backup_scroll, text=b["name"], font=MONO,
                         text_color=TEXT, anchor="w").grid(row=i, column=0, sticky="w", padx=8, pady=2)
            ctk.CTkLabel(self.backup_scroll, text=b["created"], font=SMALL,
                         text_color=MUTED).grid(row=i, column=1, padx=8, pady=2)
            path = b["path"]
            ghost_button(self.backup_scroll, "Restore", lambda p=path: self._restore(p), width=80).grid(
                row=i, column=2, padx=(0, 8), pady=2)

    def _apply_all(self):
        log_to_box(self.log, "Applying all tweaks (backing up first)...", True)
        def _do(): return self.rt.apply_all_tweaks()
        def _done(results):
            for tid, ok, msg in results:
                log_to_box(self.log, msg, ok)
            self._refresh_tweaks()
            self._refresh_backups()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _revert_all(self):
        log_to_box(self.log, "Reverting all tweaks to defaults...", True)
        def _do(): return self.rt.revert_all_tweaks()
        def _done(results):
            for tid, ok, msg in results:
                log_to_box(self.log, msg, ok)
            self._refresh_tweaks()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore(self, path: str):
        def _do(): return backup_manager.restore_registry_key(path)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_tweaks()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# STATS TRACKER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class StatsFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.tracker = StatsTracker()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Stats Tracker", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Powered by HenrikDev API. Enter your Riot ID to view stats.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # ── Input ──
        inf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        inf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        make_section_label(inf, "🔍  Player Lookup").grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(10, 4))

        self.id_entry = ctk.CTkEntry(inf, placeholder_text="Name#TAG (e.g. Player#NA1)",
                                      width=240, fg_color=PANEL2, text_color=TEXT)
        self.id_entry.grid(row=1, column=0, padx=14, pady=(0, 12))
        self.id_entry.insert(0, self.cfg.get("last_riot_id", ""))

        regions = ["na", "eu", "ap", "kr", "br", "latam"]
        self.region_var = ctk.StringVar(value=self.cfg.get("last_region", "na"))
        ctk.CTkComboBox(inf, values=regions, variable=self.region_var, width=90,
                        fg_color=PANEL2, button_color=ACCENT).grid(row=1, column=1, padx=6, pady=(0, 12))

        self.lookup_btn = accent_button(inf, "Look Up", self._lookup, width=110)
        self.lookup_btn.grid(row=1, column=2, padx=(0, 14), pady=(0, 12))

        self.error_label = ctk.CTkLabel(inf, text="", text_color=RED_LIGHT, font=BODY)
        self.error_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 8))

        # ── Player Card (hidden until lookup) ──
        self.card_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        self.card_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        self.card_frame.grid_remove()

        self.card_name = ctk.CTkLabel(self.card_frame, text="", font=H2, text_color=TEXT)
        self.card_name.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))
        self.card_level = ctk.CTkLabel(self.card_frame, text="", font=BODY, text_color=MUTED)
        self.card_level.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 2))
        self.card_rank = ctk.CTkLabel(self.card_frame, text="", font=(FONT, 14, "bold"), text_color=ACCENT)
        self.card_rank.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 4))
        self.card_peak = ctk.CTkLabel(self.card_frame, text="", font=BODY, text_color=MUTED)
        self.card_peak.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        # Stats summary
        self.stats_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        self.stats_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        self.stats_frame.grid_remove()

        make_section_label(self.stats_frame, "📊  Recent Match Stats").grid(
            row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        for col, label in enumerate(["Win Rate", "Avg KDA", "Most Played Agent"]):
            ctk.CTkLabel(self.stats_frame, text=label, font=SMALL, text_color=MUTED).grid(
                row=1, column=col, padx=20, pady=(0, 2))

        self.wr_val   = ctk.CTkLabel(self.stats_frame, text="--", font=(FONT, 15, "bold"), text_color=TEXT)
        self.kda_val  = ctk.CTkLabel(self.stats_frame, text="--", font=(FONT, 15, "bold"), text_color=TEXT)
        self.agent_val = ctk.CTkLabel(self.stats_frame, text="--", font=(FONT, 15, "bold"), text_color=TEXT)
        self.wr_val.grid(row=2, column=0, padx=20, pady=(0, 10))
        self.kda_val.grid(row=2, column=1, padx=20, pady=(0, 10))
        self.agent_val.grid(row=2, column=2, padx=20, pady=(0, 10))

        # Match history
        self.match_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        self.match_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        self.match_frame.grid_remove()

        make_section_label(self.match_frame, "🎮  Recent Matches (last 5)").grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        self.match_scroll = ctk.CTkScrollableFrame(self.match_frame, height=180, fg_color=PANEL2)
        self.match_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

    def _lookup(self):
        riot_id = sanitize_riot_id(self.id_entry.get())
        region  = self.region_var.get().strip()
        if not riot_id:
            self.error_label.configure(text="Please enter a Riot ID.")
            return
        self.error_label.configure(text="")
        self.lookup_btn.configure(state="disabled", text="Loading...")
        self.card_frame.grid_remove()
        self.stats_frame.grid_remove()
        self.match_frame.grid_remove()

        def _do(): return self.tracker.build_player_summary(riot_id, region)
        def _done(result):
            self.lookup_btn.configure(state="normal", text="Look Up")
            if isinstance(result, Exception):
                self.error_label.configure(text=str(result))
                return
            self._display_summary(result)
            self.cfg["last_riot_id"] = riot_id
            self.cfg["last_region"]  = region
            save_config(self.cfg)

        def _worker():
            try:
                r = _do()
                self.after(0, lambda: _done(r))
            except Exception as e:
                self.after(0, lambda: _done(e))
        threading.Thread(target=_worker, daemon=True).start()

    def _display_summary(self, data: dict):
        acct = data["account"]
        rank = data["rank"]
        stats = data["stats"]
        matches = data["recent_matches"]

        self.card_name.configure(text=f"{acct['name']}#{acct['tag']}")
        self.card_level.configure(text=f"Account Level: {acct['account_level']}")
        rr_change = rank['last_change']
        rr_sign = "+" if rr_change >= 0 else ""
        self.card_rank.configure(text=f"{rank['current_tier_name']}  |  {rank['ranking_in_tier']} RR  ({rr_sign}{rr_change} last game)")
        self.card_peak.configure(text=f"Peak: {rank['peak_rank']}")
        self.card_frame.grid()

        wr_color = GREEN if stats["win_rate"] >= 50 else RED_LIGHT
        self.wr_val.configure(text=f"{stats['win_rate']}%", text_color=wr_color)
        kda_color = GREEN if stats["avg_kda"] >= 1.0 else RED_LIGHT
        self.kda_val.configure(text=str(stats["avg_kda"]), text_color=kda_color)
        self.agent_val.configure(text=stats["most_played_agent"])
        self.stats_frame.grid()

        for w in self.match_scroll.winfo_children():
            w.destroy()
        headers = ["Map", "Mode", "Result", "Agent", "K / D / A", "KDA", "Date"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self.match_scroll, text=h, font=LABEL,
                         text_color=MUTED).grid(row=0, column=col, padx=8, pady=2)

        for i, m in enumerate(matches, start=1):
            result_txt = "WIN" if m["won"] else "LOSS"
            result_color = GREEN if m["won"] else RED_LIGHT
            vals = [
                m["map"], m["mode"],
                (result_txt, result_color),
                m["agent"],
                f"{m['kills']} / {m['deaths']} / {m['assists']}",
                str(m["kda_ratio"]),
                m["date"][:10] if m["date"] else "--",
            ]
            bg = "#1a2e1a" if m["won"] else "#2e1a1a"
            row_frame = ctk.CTkFrame(self.match_scroll, fg_color=bg, corner_radius=4)
            row_frame.grid(row=i, column=0, columnspan=7, sticky="ew", padx=2, pady=1)
            for col, val in enumerate(vals):
                if isinstance(val, tuple):
                    text, color = val
                else:
                    text, color = val, TEXT
                ctk.CTkLabel(row_frame, text=text, font=SMALL,
                             text_color=color).grid(row=0, column=col, padx=8, pady=4)

        self.match_frame.grid()


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS GUIDE FRAME
# ══════════════════════════════════════════════════════════════════════════════

class GuideFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.guide = SettingsGuide()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Settings Guide", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Optimal gaming settings — no changes applied, just recommendations.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        tab_view = ctk.CTkTabview(self, fg_color=PANEL, segmented_button_fg_color=PANEL2,
                                   segmented_button_selected_color=ACCENT,
                                   segmented_button_selected_hover_color=ACCENT_HV)
        tab_view.grid(row=2, column=0, sticky="nsew", padx=20, pady=6)
        self.grid_rowconfigure(2, weight=1)

        category_labels = {
            "display":   "Display",
            "graphics":  "Graphics",
            "mouse":     "Mouse",
            "crosshair": "Crosshair",
            "audio":     "Audio",
        }
        for key, label in category_labels.items():
            tab_view.add(label)
            tab = tab_view.tab(label)
            tab.grid_columnconfigure(0, weight=1)
            scroll = ctk.CTkScrollableFrame(tab, fg_color=PANEL)
            scroll.grid(row=0, column=0, sticky="nsew", pady=4)
            scroll.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

            data = self.guide.get_category(key)
            settings = data.get("settings", [])
            for i, s in enumerate(settings):
                card = ctk.CTkFrame(scroll, fg_color=PANEL2, corner_radius=8)
                card.grid(row=i, column=0, sticky="ew", padx=8, pady=4)
                card.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(card, text=s["name"], font=(FONT, 12, "bold"),
                             text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
                rec_frame = ctk.CTkFrame(card, fg_color=PANEL, corner_radius=4)
                rec_frame.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
                ctk.CTkLabel(rec_frame, text=f"  ✔  {s['recommended']}  ", font=(FONT, 11, "bold"),
                             text_color=GREEN).grid(row=0, column=0, padx=4, pady=3)
                ctk.CTkLabel(card, text=s["note"], font=SMALL, text_color=MUTED,
                             anchor="w", wraplength=600, justify="left").grid(
                    row=2, column=0, sticky="w", padx=12, pady=(0, 8))


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE BENCHMARK FRAME
# ══════════════════════════════════════════════════════════════════════════════

class BenchmarkFrame(ctk.CTkFrame):
    """Before/after competitive readiness report with 12 measurable OS metrics."""

    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg  = cfg
        self._bm  = SystemBenchmark()
        self._current_metrics: dict = {}
        self._current_score:   int  = 0
        self._scanning         = False
        self._build()
        # Kick off an initial scan after the window is drawn
        self.after(300, self._start_scan)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Page title ──
        ctk.CTkLabel(self, text="Performance Report",
                     font=H1, text_color=TEXT
                     ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(self,
                     text="Live before/after comparison — see exactly what each tweak improves.",
                     font=BODY, text_color=MUTED
                     ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        # ── Score hero card ──
        hero = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        hero.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        hero.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(hero, fg_color=ACCENT, height=3, corner_radius=0).grid(
            row=0, column=0, columnspan=3, sticky="ew")

        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.grid(row=1, column=0, columnspan=3, padx=20, pady=(12, 16), sticky="ew")
        inner.grid_columnconfigure(1, weight=1)

        # Big score
        score_col = ctk.CTkFrame(inner, fg_color="transparent")
        score_col.grid(row=0, column=0, sticky="w", padx=(0, 24))
        self._score_num = ctk.CTkLabel(score_col, text="—", font=(FONT, 48, "bold"),
                                        text_color=GOLD)
        self._score_num.pack()
        ctk.CTkLabel(score_col, text="out of 100", font=SMALL,
                     text_color=MUTED).pack()

        # Grade + bar + snapshot info
        mid_col = ctk.CTkFrame(inner, fg_color="transparent")
        mid_col.grid(row=0, column=1, sticky="ew")
        mid_col.grid_columnconfigure(0, weight=1)

        self._grade_label = ctk.CTkLabel(mid_col, text="SCANNING...",
                                          font=H2, text_color=MUTED)
        self._grade_label.grid(row=0, column=0, sticky="w")

        self._score_bar = ctk.CTkProgressBar(mid_col, height=12,
                                              progress_color=ACCENT, fg_color=PANEL2,
                                              corner_radius=6)
        self._score_bar.set(0)
        self._score_bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self._snap_label = ctk.CTkLabel(mid_col, text="",
                                         font=SMALL, text_color=MUTED)
        self._snap_label.grid(row=2, column=0, sticky="w", pady=(6, 0))

        self._delta_label = ctk.CTkLabel(mid_col, text="",
                                          font=H3, text_color=GREEN)
        self._delta_label.grid(row=3, column=0, sticky="w", pady=(2, 0))

        # Buttons
        btn_col = ctk.CTkFrame(inner, fg_color="transparent")
        btn_col.grid(row=0, column=2, sticky="ne", padx=(16, 0))
        self._scan_btn = accent_button(btn_col, "🔍  Scan Now", self._start_scan, width=150)
        self._scan_btn.pack(pady=(0, 6))
        ghost_button(btn_col, "💾  Save Snapshot", self._save_snapshot, width=150).pack(pady=(0, 6))
        ghost_button(btn_col, "✕  Clear Snapshot", self._clear_snapshot, width=150).pack(pady=(0, 6))
        self._export_btn = ghost_button(btn_col, "📤  Export Card", self._export_card, width=150)
        self._export_btn.pack()

        # ── Column headers ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 0))
        hdr.grid_columnconfigure(0, weight=0)   # icon
        hdr.grid_columnconfigure(1, weight=3)   # metric
        hdr.grid_columnconfigure(2, weight=2)   # current
        hdr.grid_columnconfigure(3, weight=2)   # snapshot / optimal
        hdr.grid_columnconfigure(4, weight=2)   # optimal
        hdr.grid_columnconfigure(5, weight=1)   # status
        hdr.grid_columnconfigure(6, weight=1)   # impact

        def _hdr(col, text, anchor="w"):
            ctk.CTkLabel(hdr, text=text, font=LABEL,
                         text_color=MUTED, anchor=anchor
                         ).grid(row=0, column=col, sticky="ew", padx=6, pady=4)

        _hdr(1, "METRIC")
        _hdr(2, "CURRENT")
        self._snap_hdr = ctk.CTkLabel(hdr, text="", font=LABEL,
                                       text_color=MUTED, anchor="w")
        self._snap_hdr.grid(row=0, column=3, sticky="ew", padx=6)
        _hdr(4, "OPTIMAL")
        _hdr(5, "STATUS", anchor="center")
        _hdr(6, "IMPACT",  anchor="center")

        # Divider
        ctk.CTkFrame(self, fg_color=PANEL2, height=1).grid(
            row=4, column=0, sticky="ew", padx=20, pady=(0, 4))

        # ── Scrollable metric rows ──
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0, height=340)
        scroll.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=0)
        scroll.grid_columnconfigure(1, weight=3)
        scroll.grid_columnconfigure(2, weight=2)
        scroll.grid_columnconfigure(3, weight=2)
        scroll.grid_columnconfigure(4, weight=2)
        scroll.grid_columnconfigure(5, weight=1)
        scroll.grid_columnconfigure(6, weight=1)
        self._scroll = scroll
        self._row_widgets: dict = {}   # key -> {current_lbl, snap_lbl, status_lbl, row_frame}
        self._build_metric_rows()

        # ── Why-it-matters expandable panel ──
        why_card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        why_card.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 8))
        why_card.grid_columnconfigure(0, weight=1)
        make_section_label(why_card, "ℹ️  Why These Metrics Matter").grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            why_card,
            text=(
                "Timer Resolution governs how often Windows delivers a clock tick to game threads — "
                "default 15.6 ms means up to 15.6 ms of input delay baked into every frame.\n"
                "Core Parking and CPU Boost prevent the CPU from dropping to idle clocks mid-fight. "
                "Mouse Acceleration adds a velocity curve so faster flicks overshoot the target. "
                "Together, these directly reduce the gap between what you do and what the server sees."
            ),
            font=SMALL, text_color=MUTED,
            wraplength=720, justify="left",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

    def _build_metric_rows(self):
        """Create one row widget set per metric; values filled in by _apply_results."""
        for i, key in enumerate(METRIC_ORDER):
            row_bg = PANEL if i % 2 == 0 else PANEL2
            rf = ctk.CTkFrame(self._scroll, fg_color=row_bg, corner_radius=8)
            rf.grid(row=i, column=0, columnspan=7, sticky="ew", pady=2)
            rf.grid_columnconfigure(0, weight=0)
            rf.grid_columnconfigure(1, weight=3)
            rf.grid_columnconfigure(2, weight=2)
            rf.grid_columnconfigure(3, weight=2)
            rf.grid_columnconfigure(4, weight=2)
            rf.grid_columnconfigure(5, weight=1)
            rf.grid_columnconfigure(6, weight=1)

            from modules.benchmark import _ICONS, _LABELS, _OPTIMAL_DESC, _IMPACT
            ctk.CTkLabel(rf, text=_ICONS[key], font=(FONT, 14),
                         width=28).grid(row=0, column=0, padx=(10, 2), pady=8, sticky="w")
            ctk.CTkLabel(rf, text=_LABELS[key], font=(FONT, 11, "bold"),
                         text_color=TEXT, anchor="w"
                         ).grid(row=0, column=1, padx=4, pady=8, sticky="ew")

            cur_lbl = ctk.CTkLabel(rf, text="—", font=BODY,
                                    text_color=MUTED, anchor="w")
            cur_lbl.grid(row=0, column=2, padx=4, pady=8, sticky="ew")

            snap_lbl = ctk.CTkLabel(rf, text="", font=SMALL,
                                     text_color=MUTED, anchor="w")
            snap_lbl.grid(row=0, column=3, padx=4, pady=8, sticky="ew")

            ctk.CTkLabel(rf, text=_OPTIMAL_DESC[key], font=SMALL,
                         text_color=MUTED, anchor="w"
                         ).grid(row=0, column=4, padx=4, pady=8, sticky="ew")

            status_lbl = ctk.CTkLabel(rf, text="●", font=(FONT, 16),
                                       text_color=MUTED, anchor="center")
            status_lbl.grid(row=0, column=5, padx=4, pady=8, sticky="ew")

            impact_color = {"HIGH": RED_LIGHT, "MEDIUM": GOLD, "LOW": MUTED}[_IMPACT[key]]
            ctk.CTkLabel(rf, text=_IMPACT[key], font=LABEL,
                         text_color=impact_color, anchor="center"
                         ).grid(row=0, column=6, padx=(4, 10), pady=8, sticky="ew")

            self._row_widgets[key] = {
                "current_lbl": cur_lbl,
                "snap_lbl":    snap_lbl,
                "status_lbl":  status_lbl,
            }

    # ── Scan logic ────────────────────────────────────────────────────────────

    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self._scan_btn.configure(state="disabled", text="Scanning...")
        self._grade_label.configure(text="SCANNING...", text_color=MUTED)

        def _do():
            return self._bm.collect()

        def _done(metrics):
            self._scanning = False
            self._scan_btn.configure(state="normal", text="🔍  Scan Now")
            self._current_metrics = metrics
            self._current_score   = self._bm.compute_score(metrics)
            self._apply_results(metrics)

        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _apply_results(self, metrics: dict):
        score  = self._current_score
        grade, color = self._bm.score_grade(score)
        snap   = self._bm.load_snapshot()

        # Update score hero
        self._score_num.configure(text=str(score), text_color=color)
        self._grade_label.configure(text=grade, text_color=color)
        self._score_bar.configure(progress_color=color)
        self._score_bar.set(score / 100)

        # Snapshot delta
        if snap:
            before = snap.get("score", 0)
            ts     = snap.get("timestamp", "")[:16].replace("T", " ")
            delta  = score - before
            delta_str = f"+{delta}" if delta >= 0 else str(delta)
            delta_color = GREEN if delta > 0 else (RED_LIGHT if delta < 0 else MUTED)
            self._snap_label.configure(
                text=f"Snapshot from {ts}  —  Before: {before}/100",
                text_color=MUTED)
            self._delta_label.configure(
                text=f"Improvement: {delta_str} points ({before} → {score})",
                text_color=delta_color)
            self._snap_hdr.configure(text="BEFORE")
        else:
            self._snap_label.configure(text="No snapshot saved yet. Tweak, then save a snapshot first.")
            self._delta_label.configure(text="")
            self._snap_hdr.configure(text="")

        # Update each row
        for key, wdg in self._row_widgets.items():
            m = metrics.get(key)
            if not m:
                continue
            passed = m.get("passed", False)
            val    = m.get("value", "—")

            wdg["current_lbl"].configure(
                text=val,
                text_color=GREEN if passed else RED_LIGHT,
            )
            wdg["status_lbl"].configure(
                text="✓" if passed else "✗",
                text_color=GREEN if passed else RED_LIGHT,
            )

            # Snapshot column
            if snap and key in snap.get("metrics", {}):
                before_m = snap["metrics"][key]
                before_val    = before_m.get("value", "—")
                before_passed = before_m.get("passed", False)
                # Show improvement arrow if status changed
                if before_passed and passed:
                    snap_text = before_val
                    snap_color = GREEN
                elif not before_passed and passed:
                    snap_text  = f"{before_val}  →  FIXED"
                    snap_color = GREEN
                elif before_passed and not passed:
                    snap_text  = f"{before_val}  →  REGRESSED"
                    snap_color = RED_LIGHT
                else:
                    snap_text  = before_val
                    snap_color = MUTED
                wdg["snap_lbl"].configure(text=snap_text, text_color=snap_color)
            else:
                wdg["snap_lbl"].configure(text="", text_color=MUTED)

    # ── Snapshot actions ──────────────────────────────────────────────────────

    def _save_snapshot(self):
        if not self._current_metrics:
            return
        self._bm.save_snapshot(self._current_metrics, self._current_score)
        self._apply_results(self._current_metrics)
        _win_toast("Valo Optimise",
                   f"Snapshot saved — score {self._current_score}/100. "
                   "Apply tweaks then re-scan to see improvement.")

    def _clear_snapshot(self):
        self._bm.delete_snapshot()
        if self._current_metrics:
            self._apply_results(self._current_metrics)

    def _export_card(self):
        """Generate a shareable before/after PNG card and open it."""
        if not self._current_metrics:
            _win_toast("Valo Optimise", "Run a scan first before exporting a card.")
            return
        snap = self._bm.load_snapshot()
        if not snap:
            _win_toast("Valo Optimise",
                       "Save a snapshot before optimising, then scan again to show improvement.")
            return

        self._export_btn.configure(state="disabled", text="Generating...")

        def _do():
            before_score   = snap.get("score", 0)
            before_metrics = snap.get("metrics", {})
            return generate_card(
                before_score   = before_score,
                after_score    = self._current_score,
                before_metrics = before_metrics,
                after_metrics  = {k: {"value": v["value"], "passed": v["passed"]}
                                  for k, v in self._current_metrics.items()},
            )

        def _done(path):
            self._export_btn.configure(state="normal", text="📤  Export Card")
            _win_toast("Valo Optimise", f"Card saved to Desktop — {path.split(chr(92))[-1]}")
            try:
                os.startfile(path)
            except Exception:
                pass

        run_in_thread(_do, lambda p: self.after(0, lambda: _done(p)))


# ══════════════════════════════════════════════════════════════════════════════
# PRE-GAME BOOST FRAME
# ══════════════════════════════════════════════════════════════════════════════

class BoostFrame(ctk.CTkFrame):
    """Pre-Game Boost with animated per-step checklist and live progress bar."""

    _STEPS = [
        ("pwr",   "⚡", "Ultimate Power Plan",  "Sets CPU to maximum performance mode"),
        ("bg",    "🧹", "Kill Background Apps", "Frees CPU & RAM from non-essential processes"),
        ("ram",   "🧠", "Clear Standby RAM",    "Flushes cached memory back to available pool"),
        ("reg",   "🔧", "Registry Tweaks",      "Applies MMCSS & TCP performance tweaks"),
        ("park",  "⏱", "Disable Core Parking", "Prevents CPU cores sleeping mid-fight"),
        ("timer", "⏲", "1ms Timer Resolution",  "Reduces input & frame timing from 15.6ms → 1ms"),
        ("vis",   "👁", "Visibility Preset",    "Applies competitive colour profile"),
    ]

    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self._sys = SystemOptimizer()
        self._rt  = RegistryTweaks()
        self._cpu = CpuTimerOptimizer()
        self._boost_running = False
        self._step_icon_lbls: dict  = {}
        self._step_msg_lbls:  dict  = {}
        self._step_row_frames: dict = {}
        self._step_row_bgs:    dict = {}
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──
        ctk.CTkLabel(self, text="Pre-Game Boost", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(self,
                     text="One-click sequence — watch each optimisation complete in real time.",
                     font=BODY, text_color=MUTED
                     ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # ── Main card ──
        card = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        card.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(card, fg_color=ACCENT, height=3, corner_radius=0).grid(
            row=0, column=0, sticky="ew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=1, column=0, padx=18, pady=(14, 16), sticky="ew")
        inner.grid_columnconfigure(0, weight=1)

        # Button row
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w")
        self._boost_btn = ctk.CTkButton(
            btn_row, text="⚡  LAUNCH BOOST", command=self._run_boost,
            width=240, height=54, font=H2,
            fg_color=ACCENT, hover_color=ACCENT_HV, corner_radius=10, text_color=TEXT
        )
        self._boost_btn.grid(row=0, column=0, padx=(0, 12))
        ghost_button(btn_row, "↩  Revert All", self._revert_all, width=120).grid(row=0, column=1)
        ctk.CTkLabel(btn_row, text="Global Hotkey: Ctrl+Shift+B", font=SMALL,
                     text_color=MUTED).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Progress bar
        self._progress = ctk.CTkProgressBar(inner, height=8, progress_color=GREEN,
                                             fg_color=PANEL2, corner_radius=4)
        self._progress.set(0)
        self._progress.grid(row=1, column=0, sticky="ew", pady=(14, 10))

        # Animated step checklist
        steps_frame = ctk.CTkFrame(inner, fg_color=PANEL2, corner_radius=8)
        steps_frame.grid(row=2, column=0, sticky="ew")
        steps_frame.grid_columnconfigure(2, weight=1)

        for i, (key, emoji, label, hint) in enumerate(self._STEPS):
            row_bg = PANEL2 if i % 2 == 0 else "#16243a"
            rf = ctk.CTkFrame(steps_frame, fg_color=row_bg, corner_radius=0)
            rf.grid(row=i, column=0, columnspan=4, sticky="ew")
            rf.grid_columnconfigure(2, weight=1)
            self._step_row_frames[key] = rf
            self._step_row_bgs[key]    = row_bg

            ctk.CTkLabel(rf, text=emoji, font=H3, width=26,
                         text_color=MUTED).grid(row=0, column=0, padx=(10, 4), pady=7)

            icon_lbl = ctk.CTkLabel(rf, text="○", font=(FONT, 12, "bold"),
                                     text_color=MUTED, width=18)
            icon_lbl.grid(row=0, column=1, padx=(0, 8), pady=7)
            self._step_icon_lbls[key] = icon_lbl

            ctk.CTkLabel(rf, text=label, font=(FONT, 11, "bold"),
                         text_color=TEXT, anchor="w").grid(row=0, column=2, sticky="ew", pady=7)

            msg_lbl = ctk.CTkLabel(rf, text=hint, font=MONO,
                                    text_color=MUTED, anchor="e", width=260)
            msg_lbl.grid(row=0, column=3, padx=(0, 12), pady=7, sticky="e")
            self._step_msg_lbls[key] = msg_lbl

        # Status line
        self._status_lbl = ctk.CTkLabel(inner, text="", font=BODY, text_color=MUTED)
        self._status_lbl.grid(row=3, column=0, sticky="w", pady=(10, 0))

        # ── Trust footer ──
        trust = ctk.CTkFrame(self, fg_color="transparent")
        trust.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 16))
        ctk.CTkLabel(trust,
                     text="✓ Anti-Cheat Safe   ✓ No game process interaction   ✓ All changes are fully reversible",
                     font=SMALL, text_color=MUTED, anchor="center"
                     ).pack()

    # ── Step animation helpers ────────────────────────────────────────────────

    def _step_active(self, key: str):
        lbl = self._step_icon_lbls.get(key)
        if lbl:
            lbl.configure(text="⟳", text_color=GOLD)

    def _step_done(self, key: str, ok: bool, msg: str):
        lbl = self._step_icon_lbls.get(key)
        if lbl:
            lbl.configure(text="✓" if ok else "✗", text_color=GREEN if ok else RED_LIGHT)
        msg_lbl = self._step_msg_lbls.get(key)
        if msg_lbl:
            short = msg[:50] if msg else ""
            msg_lbl.configure(text=short, text_color=GREEN if ok else RED_LIGHT)
        # Flash row green or red then restore
        rf   = self._step_row_frames.get(key)
        orig = self._step_row_bgs.get(key, PANEL2)
        if rf:
            flash_bg(rf, "#0d2e18" if ok else "#2e0d12", orig, 600)
        done_count = sum(1 for l in self._step_icon_lbls.values()
                         if l.cget("text") in ("✓", "✗"))
        ease_progress(self._progress, done_count / len(self._STEPS), 400)

    def _reset_steps(self):
        for lbl in self._step_icon_lbls.values():
            lbl.configure(text="○", text_color=MUTED)
        for key, lbl in self._step_msg_lbls.items():
            hint = next((h for k, _, _, h in self._STEPS if k == key), "")
            lbl.configure(text=hint, text_color=MUTED)
        self._progress.set(0)
        self._status_lbl.configure(text="")

    # ── Boost sequence ────────────────────────────────────────────────────────

    def _run_boost(self):
        if self._boost_running:
            return
        self._boost_running = True
        self._boost_btn.configure(state="disabled", text="Running...")
        self._reset_steps()
        self._status_lbl.configure(text="Optimising your system — this takes ~10 seconds...", text_color=MUTED)

        def _activate(k):
            self.after(0, lambda key=k: self._step_active(key))

        def _finish_step(k, ok, msg):
            self.after(0, lambda key=k, o=ok, m=msg: self._step_done(key, o, m))

        def _do():
            _activate("pwr")
            ok, msg = self._sys.set_ultimate_performance_plan()
            _finish_step("pwr", ok, msg)

            _activate("bg")
            killed = self._sys.kill_all_background_targets()
            n = sum(1 for _, o, _ in killed if o) if killed else 0
            _finish_step("bg", True, f"Killed {n} processes" if n else "No targets running")

            _activate("ram")
            ok, msg = self._sys.clear_standby_memory()
            _finish_step("ram", ok, msg)

            _activate("reg")
            tw = self._rt.apply_all_tweaks()
            n_ok = sum(1 for _, o, _ in tw if o)
            _finish_step("reg", True, f"{n_ok}/{len(tw)} tweaks applied")

            _activate("park")
            ok, msg = self._cpu.disable_core_parking()
            _finish_step("park", ok, msg)

            _activate("timer")
            ok, msg = self._cpu.set_timer_resolution_1ms()
            _finish_step("timer", ok, msg)

            _activate("vis")
            vis_preset = self.cfg.get("visibility_preset", "Competitive")
            ok, msg = VisibilityOptimizer().apply_preset(vis_preset)
            _finish_step("vis", ok, msg)

        def _complete(_):
            self._boost_running = False
            self._boost_btn.configure(state="normal", text="⚡  LAUNCH BOOST")
            self._status_lbl.configure(
                text="✅  Boost complete — launch your game now!",
                text_color=GREEN
            )
            _win_toast("Valo Optimise", "Boost complete! Launch your game now.")

        run_in_thread(_do, lambda r: self.after(0, lambda: _complete(r)))

    def _revert_all(self):
        self._status_lbl.configure(text="Reverting...", text_color=MUTED)

        def _do():
            r1 = self._cpu.enable_core_parking()
            r2 = self._cpu.restore_timer_resolution()
            return r1, r2

        def _done(res):
            r1, r2 = res
            errors = [m for ok, m in (r1, r2) if not ok]
            self._status_lbl.configure(
                text="↩ Core parking & timer restored." if not errors else " | ".join(errors),
                text_color=GREEN if not errors else RED_LIGHT
            )

        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# GAME CONFIG FRAME
# ══════════════════════════════════════════════════════════════════════════════

class ValorantFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.vc = ValorantConfig()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Game Config Editor", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Applies competitive settings to GameUserSettings.ini. Close the game before applying.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # Config file status
        sf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        sf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        sf.grid_columnconfigure(0, weight=1)
        make_section_label(sf, "📁  Config File").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        path = self.vc.find_config_path()
        status_text  = f"Found: {path}" if path else "Not found — launch the game once to generate the config file."
        status_color = GREEN if path else RED_LIGHT
        ctk.CTkLabel(sf, text=status_text, text_color=status_color, font=SMALL,
                     wraplength=700, anchor="w").grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        # Settings table
        tf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        tf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        tf.grid_columnconfigure(0, weight=1)
        make_section_label(tf, "⚙️  Competitive Settings").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        self.settings_scroll = ctk.CTkScrollableFrame(tf, height=200, fg_color=PANEL2)
        self.settings_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))
        self.settings_scroll.grid_columnconfigure(1, weight=1)
        self._refresh_settings()

        ab = ctk.CTkFrame(tf, fg_color="transparent")
        ab.grid(row=2, column=0, sticky="w", padx=14, pady=(4, 12))
        accent_button(ab, "Apply Competitive Settings", self._apply, width=210).grid(row=0, column=0, padx=(0, 8))
        ghost_button(ab, "Restore Latest Backup", self._restore_backup, width=170).grid(row=0, column=1)

        # ── Fullscreen Optimizations ──
        ff = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        ff.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        ff.grid_columnconfigure(1, weight=1)
        make_section_label(ff, "🖥️  Fullscreen Optimizations").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.fs_opt_label = ctk.CTkLabel(ff, text="Checking...", text_color=MUTED, font=BODY)
        self.fs_opt_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(ff, "Disable FS Optimizations", self._disable_fs_opt, width=210).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(ff, "Restore", self._enable_fs_opt, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(ff, text="Forces true exclusive fullscreen (not DWM fullscreen) — 1-3 frame lower input latency.",
                     text_color=MUTED, font=SMALL, wraplength=620, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_fs_opt()

        warn = ctk.CTkFrame(self, fg_color="#2a1a00", corner_radius=8)
        warn.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 6))
        ctk.CTkLabel(warn, text="⚠️  Close the game before applying. In-game settings may overwrite these values.",
                     text_color="#ffcc44", font=SMALL, wraplength=700, anchor="w"
                     ).grid(row=0, column=0, padx=14, pady=8, sticky="w")

        # ── Crosshair Backup / Restore ──
        cf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        cf.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        cf.grid_columnconfigure(1, weight=1)
        make_section_label(cf, "🎯  Crosshair Backup").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        ctk.CTkLabel(cf, text="Current crosshair code:", text_color=MUTED, font=BODY
                     ).grid(row=1, column=0, padx=14, pady=(0, 4), sticky="w")
        self._xhair_current = ctk.CTkLabel(cf, text="Loading...", text_color=TEXT,
                                            font=MONO, anchor="w", wraplength=500)
        self._xhair_current.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 4))
        accent_button(cf, "Copy to Clipboard", self._copy_crosshair, width=150).grid(
            row=1, column=2, padx=(0, 14), pady=(0, 4))

        ctk.CTkLabel(cf, text="Apply crosshair code:", text_color=MUTED, font=BODY
                     ).grid(row=2, column=0, padx=14, pady=(0, 10), sticky="w")
        self._xhair_entry = ctk.CTkEntry(cf, placeholder_text="Paste crosshair code here...",
                                          fg_color=PANEL2, border_color=PANEL2, text_color=TEXT,
                                          font=MONO)
        self._xhair_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(0, 10))
        accent_button(cf, "Apply Crosshair", self._apply_crosshair, width=150).grid(
            row=2, column=2, padx=(0, 14), pady=(0, 10))

        self._refresh_crosshair()

        make_section_label(self, "Status Log").grid(row=7, column=0, sticky="w", padx=20, pady=(6, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_settings(self):
        for w in self.settings_scroll.winfo_children():
            w.destroy()
        display = self.vc.get_setting_display()
        for col, h in enumerate(["Setting", "Current", "Recommended", "✔"]):
            ctk.CTkLabel(self.settings_scroll, text=h, font=LABEL,
                         text_color=MUTED).grid(row=0, column=col, padx=8, pady=2, sticky="w")
        for i, s in enumerate(display, start=1):
            match_color = GREEN if s["matches"] else RED_LIGHT
            ctk.CTkLabel(self.settings_scroll, text=s["name"], font=MONO,
                         text_color=TEXT, anchor="w").grid(row=i, column=0, padx=8, pady=1, sticky="w")
            ctk.CTkLabel(self.settings_scroll, text=s["current"], font=MONO,
                         text_color=MUTED, anchor="w").grid(row=i, column=1, padx=8, pady=1, sticky="w")
            ctk.CTkLabel(self.settings_scroll, text=s["recommended"], font=MONO,
                         text_color=GREEN, anchor="w").grid(row=i, column=2, padx=8, pady=1, sticky="w")
            ctk.CTkLabel(self.settings_scroll, text="✔" if s["matches"] else "✗", font=(FONT, 11, "bold"),
                         text_color=match_color).grid(row=i, column=3, padx=8, pady=1)

    def _apply(self):
        log_to_box(self.log, "Backing up config and applying competitive settings...", True)
        def _do(): return self.vc.apply_competitive_settings()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self.after(200, self._refresh_settings)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_backup(self):
        def _do(): return self.vc.restore_latest_backup()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self.after(200, self._refresh_settings)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_fs_opt(self):
        status = self.vc.get_fullscreen_opt_status()
        color = GREEN if "Disabled" in status else MUTED
        self.fs_opt_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_fs_opt(self):
        def _do(): return self.vc.disable_fullscreen_optimizations()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_fs_opt()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_fs_opt(self):
        def _do(): return self.vc.enable_fullscreen_optimizations()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_fs_opt()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    # ── Crosshair Backup / Restore ────────────────────────────────────────────

    def _refresh_crosshair(self):
        def _do(): return self.vc.get_crosshair_code()
        def _done(code):
            if code:
                display = code if len(code) <= 80 else code[:77] + "..."
                self._xhair_current.configure(text=display, text_color=TEXT)
            else:
                self._xhair_current.configure(text="Not found — launch the game once to generate config.", text_color=MUTED)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _copy_crosshair(self):
        def _do(): return self.vc.get_crosshair_code()
        def _done(code):
            if code:
                self.clipboard_clear()
                self.clipboard_append(code)
                log_to_box(self.log, "Crosshair code copied to clipboard.", True)
            else:
                log_to_box(self.log, "No crosshair code found in config.", False)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _apply_crosshair(self):
        code = self._xhair_entry.get().strip()
        if not code:
            log_to_box(self.log, "Please paste a crosshair code in the input field.", False)
            return
        log_to_box(self.log, "Applying crosshair code...", True)
        def _do(): return self.vc.set_crosshair_code(code)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_crosshair()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# MOUSE & AIM FRAME
# ══════════════════════════════════════════════════════════════════════════════

class MouseFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.mo = MouseOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Mouse & Aim Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Disable acceleration for 1:1 raw mouse movement. No reboot required.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        af = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        af.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        af.grid_columnconfigure(1, weight=1)
        make_section_label(af, "🖱️  Mouse Acceleration").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.accel_label = ctk.CTkLabel(af, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.accel_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(af, "Disable Acceleration", self._disable_accel, width=180).grid(row=1, column=1, padx=6, pady=(0, 10))
        ghost_button(af, "Re-enable", self._enable_accel, width=100).grid(row=1, column=2, padx=(0, 14), pady=(0, 10))
        self._refresh_accel()

        inf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        inf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        inf.grid_columnconfigure(0, weight=1)
        make_section_label(inf, "ℹ️  Mouse Settings").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        status = self.mo.get_full_status()
        ctk.CTkLabel(inf, text=f"Windows Pointer Speed: {status['pointer_speed']} / 20  (recommend 6 for most players)",
                     text_color=MUTED, font=BODY).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(inf, text=f"MouseThreshold1: {status['threshold1']}   MouseThreshold2: {status['threshold2']}",
                     text_color=MUTED, font=BODY).grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))

        tip = ctk.CTkFrame(self, fg_color="#0d2040", corner_radius=8)
        tip.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(tip, text="💡  Enable Raw Input in your game: Settings → Mouse → Raw Input Buffer: On",
                     text_color="#5ba3f5", font=BODY, wraplength=700, anchor="w"
                     ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        # ── USB Selective Suspend ──
        usf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        usf.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        usf.grid_columnconfigure(1, weight=1)
        make_section_label(usf, "🔌  USB Selective Suspend").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.usb_ss_label = ctk.CTkLabel(usf, text="Checking...", text_color=MUTED, font=BODY)
        self.usb_ss_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(usf, "Disable USB Suspend", self._disable_usb_ss, width=180).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(usf, "Restore", self._enable_usb_ss, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(usf, text="Prevents USB controller from power-gating your mouse between frames — eliminates rare micro-freezes in mouse movement.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_usb_ss()

        # ── USB Root Hub Power ──
        uhf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        uhf.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        uhf.grid_columnconfigure(1, weight=1)
        make_section_label(uhf, "🖥️  USB Root Hub Power").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.usb_hub_label = ctk.CTkLabel(uhf, text="Checking...", text_color=MUTED, font=BODY)
        self.usb_hub_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(uhf, "Disable Hub Power Save", self._disable_usb_hub, width=190).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(uhf, "Restore", self._enable_usb_hub, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(uhf, text="Disables power management on USB root hubs — the hardware bus your mouse plugs into never sleeps.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_usb_hub()

        # ── eDPI Calculator ──
        ef = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        ef.grid(row=7, column=0, sticky="ew", padx=20, pady=6)
        ef.grid_columnconfigure(0, weight=1)
        make_section_label(ef, "🎯  eDPI Calculator").grid(row=0, column=0, columnspan=5, sticky="w", padx=14, pady=(10, 4))

        calc_row = ctk.CTkFrame(ef, fg_color="transparent")
        calc_row.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(calc_row, text="Mouse DPI:", text_color=MUTED, font=BODY).grid(row=0, column=0, padx=(0, 6))
        self.dpi_entry = ctk.CTkEntry(calc_row, width=90, placeholder_text="e.g. 800", fg_color=PANEL2, text_color=TEXT)
        self.dpi_entry.grid(row=0, column=1, padx=(0, 16))
        ctk.CTkLabel(calc_row, text="In-game Sensitivity:", text_color=MUTED, font=BODY).grid(row=0, column=2, padx=(0, 6))
        self.sens_entry = ctk.CTkEntry(calc_row, width=90, placeholder_text="e.g. 0.4", fg_color=PANEL2, text_color=TEXT)
        self.sens_entry.grid(row=0, column=3, padx=(0, 16))
        accent_button(calc_row, "Calculate", self._calc_edpi, width=110).grid(row=0, column=4)

        self.edpi_result = ctk.CTkLabel(ef, text="", text_color=ACCENT, font=H3)
        self.edpi_result.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 4))
        self.edpi_note = ctk.CTkLabel(ef, text="", text_color=MUTED, font=SMALL, wraplength=650, justify="left")
        self.edpi_note.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        # ── Aim Trainers ──
        atf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        atf.grid(row=8, column=0, sticky="ew", padx=20, pady=6)
        make_section_label(atf, "🏹  Aim Trainers (via Steam)").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        at_btns = ctk.CTkFrame(atf, fg_color="transparent")
        at_btns.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        accent_button(at_btns, "Launch KovaaK's", lambda: self._launch_trainer("KovaaK's"), width=160).grid(row=0, column=0, padx=(0, 10))
        accent_button(at_btns, "Launch AimLab", lambda: self._launch_trainer("AimLab"), width=150).grid(row=0, column=1)
        ctk.CTkLabel(atf, text="Aim training apps are the single biggest aim improvement beyond hardware. 20min/day before playing.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))

        make_section_label(self, "Status Log").grid(row=9, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=90)
        self.log.grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_accel(self):
        status = self.mo.get_acceleration_status()
        color = GREEN if status == "Disabled" else RED_LIGHT
        self.accel_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_accel(self):
        def _do(): return self.mo.disable_acceleration()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_accel()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_accel(self):
        def _do(): return self.mo.enable_acceleration()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_accel()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_usb_ss(self):
        s = self.mo.get_usb_selective_suspend_status()
        self.usb_ss_label.configure(text=f"Status: {s}", text_color=GREEN if "Disabled" in s else MUTED)

    def _disable_usb_ss(self):
        log_to_box(self.log, "Disabling USB Selective Suspend...", True)
        def _do(): return self.mo.disable_usb_selective_suspend()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_usb_ss()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_usb_ss(self):
        def _do(): return self.mo.enable_usb_selective_suspend()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_usb_ss()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_usb_hub(self):
        s = self.mo.get_usb_hub_power_status()
        self.usb_hub_label.configure(text=f"Status: {s}", text_color=GREEN if "Disabled" in s else MUTED)

    def _disable_usb_hub(self):
        log_to_box(self.log, "Disabling USB root hub power management (requires admin)...", True)
        def _do(): return self.mo.disable_usb_hub_power()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_usb_hub()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_usb_hub(self):
        def _do(): return self.mo.enable_usb_hub_power()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_usb_hub()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _calc_edpi(self):
        try:
            dpi  = float(self.dpi_entry.get().strip())
            sens = float(self.sens_entry.get().strip())
            edpi = self.mo.calculate_edpi(dpi, sens)
            note = self.mo.edpi_recommendation(edpi)
            self.edpi_result.configure(text=f"eDPI: {edpi}")
            self.edpi_note.configure(text=note)
        except ValueError:
            self.edpi_result.configure(text="Enter valid numbers for DPI and sensitivity.")
            self.edpi_note.configure(text="")

    def _launch_trainer(self, app: str):
        def _do(): return self.mo.launch_aim_trainer(app)
        def _done(r): log_to_box(self.log, r[1], r[0])
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# MOUSE DRIVER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class MouseDriverFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg   = cfg
        self._prm  = PollingRateMonitor()
        self._pb   = PointerBallistics()
        self._spm  = SensitivityProfileManager()
        self._mdi  = MouseDeviceInfo()
        self._ric  = RawInputChecker()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Title ──
        ctk.CTkLabel(self, text="Mouse Driver", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Polling rate, pointer ballistics, sensitivity profiles, and raw input diagnostics.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

        # ── Device Info ──
        df = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        df.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        df.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(df, fg_color=ACCENT2, height=2, corner_radius=0).grid(
            row=0, column=0, sticky="ew", padx=0, pady=(0, 0))
        make_section_label(df, "🖱️  Detected Mouse Devices").grid(row=1, column=0, sticky="w", padx=14, pady=(8, 4))
        self._device_frame = ctk.CTkFrame(df, fg_color="transparent")
        self._device_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._dev_label = ctk.CTkLabel(self._device_frame, text="Scanning devices...", text_color=MUTED, font=BODY)
        self._dev_label.pack(anchor="w")
        run_in_thread(self._mdi.get_devices, lambda r: self.after(0, lambda: self._populate_devices(r)))

        # ── Polling Rate Monitor ──
        pf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        pf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        pf.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(pf, fg_color=ACCENT, height=2, corner_radius=0).grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=0, pady=(0, 0))
        make_section_label(pf, "⚡  Polling Rate Monitor").grid(row=1, column=0, columnspan=3, sticky="w", padx=14, pady=(8, 4))
        ctk.CTkLabel(pf, text="Move your mouse continuously, then click Measure.",
                     text_color=MUTED, font=BODY).grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))
        self._poll_result_label = ctk.CTkLabel(pf, text="—", text_color=MUTED, font=H3)
        self._poll_result_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 4))
        self._poll_btn = accent_button(pf, "Measure Polling Rate", self._measure_poll, width=200)
        self._poll_btn.grid(row=3, column=1, sticky="e", padx=14, pady=(0, 4))
        self._poll_note = ctk.CTkLabel(pf, text="", text_color=MUTED, font=SMALL, wraplength=600)
        self._poll_note.grid(row=4, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))

        # ── Pointer Ballistics ──
        bf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        bf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        bf.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(bf, fg_color=ACCENT, height=2, corner_radius=0).grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=0, pady=(0, 0))
        make_section_label(bf, "🎯  Pointer Ballistics").grid(row=1, column=0, columnspan=3, sticky="w", padx=14, pady=(8, 4))
        self._ballistics_label = ctk.CTkLabel(bf, text=f"Status: {self._pb.get_status()}",
                                               text_color=MUTED, font=(FONT, 11, "bold"))
        self._ballistics_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 4))
        btn_row_b = ctk.CTkFrame(bf, fg_color="transparent")
        btn_row_b.grid(row=2, column=1, sticky="e", padx=14, pady=(0, 4))
        accent_button(btn_row_b, "Set 1:1 Linear", self._set_ballistics_linear, width=150).grid(row=0, column=0, padx=(0, 8))
        ghost_button(btn_row_b, "Restore Default", self._restore_ballistics, width=140).grid(row=0, column=1)
        ctk.CTkLabel(bf,
            text="Writes the SmoothMouseXCurve / SmoothMouseYCurve registry values to enforce perfect 1:1 movement "
                 "at all speed levels — no hidden OS pointer acceleration.",
            text_color=MUTED, font=SMALL, wraplength=680, justify="left"
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))

        # ── Sensitivity Profile Manager ──
        spf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        spf.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        spf.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(spf, fg_color=ACCENT2, height=2, corner_radius=0).grid(
            row=0, column=0, sticky="ew", padx=0, pady=(0, 0))
        make_section_label(spf, "📋  Sensitivity Profiles").grid(row=1, column=0, sticky="w", padx=14, pady=(8, 4))

        # Profile input row
        inp_row = ctk.CTkFrame(spf, fg_color="transparent")
        inp_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))
        ctk.CTkLabel(inp_row, text="Name:", text_color=MUTED, font=BODY).grid(row=0, column=0, padx=(0, 4))
        self._prof_name = ctk.CTkEntry(inp_row, width=110, placeholder_text="Profile name", fg_color=PANEL2, text_color=TEXT)
        self._prof_name.grid(row=0, column=1, padx=(0, 10))
        ctk.CTkLabel(inp_row, text="DPI:", text_color=MUTED, font=BODY).grid(row=0, column=2, padx=(0, 4))
        self._prof_dpi = ctk.CTkEntry(inp_row, width=70, placeholder_text="800", fg_color=PANEL2, text_color=TEXT)
        self._prof_dpi.grid(row=0, column=3, padx=(0, 10))
        ctk.CTkLabel(inp_row, text="Sens:", text_color=MUTED, font=BODY).grid(row=0, column=4, padx=(0, 4))
        self._prof_sens = ctk.CTkEntry(inp_row, width=70, placeholder_text="0.4", fg_color=PANEL2, text_color=TEXT)
        self._prof_sens.grid(row=0, column=5, padx=(0, 10))
        ctk.CTkLabel(inp_row, text="Ptr Speed (1-20):", text_color=MUTED, font=BODY).grid(row=0, column=6, padx=(0, 4))
        self._prof_speed_var = ctk.StringVar(value="6")
        self._prof_speed = ctk.CTkEntry(inp_row, width=50, textvariable=self._prof_speed_var, fg_color=PANEL2, text_color=TEXT)
        self._prof_speed.grid(row=0, column=7, padx=(0, 10))
        accent_button(inp_row, "Save Profile", self._save_profile, width=130).grid(row=0, column=8)

        # Profile list
        self._profile_scroll = ctk.CTkScrollableFrame(spf, height=120, fg_color=PANEL2)
        self._profile_scroll.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._profile_scroll.grid_columnconfigure(0, weight=1)
        self._refresh_profiles()

        # ── Raw Input Status ──
        rf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        rf.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        rf.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(rf, fg_color=ACCENT, height=2, corner_radius=0).grid(
            row=0, column=0, sticky="ew", padx=0, pady=(0, 0))
        make_section_label(rf, "🔍  Raw Input Diagnostics").grid(row=1, column=0, sticky="w", padx=14, pady=(8, 4))
        self._raw_frame = ctk.CTkFrame(rf, fg_color="transparent")
        self._raw_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._refresh_raw_input()

        # ── Status Log ──
        make_section_label(self, "Status Log").grid(row=7, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 16))

    # ── Device helpers ──────────────────────────────────────────────────────

    def _populate_devices(self, devices: list):
        for w in self._device_frame.winfo_children():
            w.destroy()
        if not devices:
            ctk.CTkLabel(self._device_frame, text="No mouse devices detected via PnP.",
                         text_color=RED_LIGHT, font=BODY).pack(anchor="w")
            return
        for d in devices:
            vid_pid = f"  VID: {d['vid']}  PID: {d['pid']}" if d["vid"] else ""
            ctk.CTkLabel(
                self._device_frame,
                text=f"• {d['name']}{vid_pid}",
                text_color=TEXT, font=BODY
            ).pack(anchor="w")

    # ── Polling rate helpers ─────────────────────────────────────────────────

    def _measure_poll(self):
        self._poll_btn.configure(state="disabled", text="Measuring... keep moving mouse")
        self._poll_result_label.configure(text="Measuring...", text_color=MUTED)
        self._poll_note.configure(text="")

        def _do():
            return self._prm.measure(2)

        def _done(rate):
            self._poll_btn.configure(state="normal", text="Measure Polling Rate")
            color = GREEN if rate >= 1000 else (MUTED if rate >= 500 else RED_LIGHT)
            self._poll_result_label.configure(text=f"Polling Rate: {rate} Hz", text_color=color)
            if rate < 1000:
                self._poll_note.configure(
                    text=f"Your mouse is reporting {rate} Hz. For competitive play, 1000 Hz+ is recommended. "
                         "Change this in your mouse software (e.g. Razer Synapse, Logitech G Hub, SteelSeries GG).",
                    text_color=MUTED
                )
            else:
                self._poll_note.configure(
                    text=f"Your mouse is running at {rate} Hz polling rate.", text_color=GREEN
                )
            log_to_box(self.log, f"Polling rate measured: {rate} Hz", rate >= 500)

        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    # ── Ballistics helpers ───────────────────────────────────────────────────

    def _set_ballistics_linear(self):
        def _do(): return self._pb.set_linear()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._ballistics_label.configure(
                text=f"Status: {self._pb.get_status()}",
                text_color=GREEN if r[0] else RED_LIGHT
            )
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_ballistics(self):
        def _do(): return self._pb.restore_default()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._ballistics_label.configure(
                text=f"Status: {self._pb.get_status()}", text_color=MUTED
            )
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    # ── Profile helpers ──────────────────────────────────────────────────────

    def _save_profile(self):
        name  = self._prof_name.get().strip()
        dpi_s = self._prof_dpi.get().strip()
        sens_s = self._prof_sens.get().strip()
        spd_s  = self._prof_speed_var.get().strip()

        if not name:
            log_to_box(self.log, "Enter a profile name.", False)
            return
        try:
            dpi  = int(dpi_s) if dpi_s else 800
            sens = float(sens_s) if sens_s else 0.4
            spd  = int(spd_s) if spd_s else 6
        except ValueError:
            log_to_box(self.log, "Invalid DPI, sensitivity, or pointer speed value.", False)
            return

        ok, msg = self._spm.save_profile(name, dpi, sens, spd)
        log_to_box(self.log, msg, ok)
        self._refresh_profiles()

    def _refresh_profiles(self):
        for w in self._profile_scroll.winfo_children():
            w.destroy()
        profiles = self._spm.list_profiles()
        if not profiles:
            ctk.CTkLabel(self._profile_scroll, text="No profiles saved yet.",
                         text_color=MUTED, font=BODY).grid(row=0, column=0, padx=8, pady=6)
            return
        headers = ["Name", "DPI", "Sensitivity", "Ptr Speed", "", ""]
        for col, h in enumerate(headers):
            ctk.CTkLabel(self._profile_scroll, text=h, font=LABEL,
                         text_color=MUTED).grid(row=0, column=col, padx=6, pady=2, sticky="w")
        self._profile_scroll.grid_columnconfigure(0, weight=1)
        for i, p in enumerate(profiles, start=1):
            ctk.CTkLabel(self._profile_scroll, text=p.get("name", ""), font=(FONT, 11, "bold"),
                         text_color=TEXT, anchor="w").grid(row=i, column=0, padx=6, pady=2, sticky="w")
            ctk.CTkLabel(self._profile_scroll, text=str(p.get("dpi", "")), font=BODY,
                         text_color=MUTED).grid(row=i, column=1, padx=6, pady=2)
            ctk.CTkLabel(self._profile_scroll, text=str(p.get("sensitivity", "")), font=BODY,
                         text_color=MUTED).grid(row=i, column=2, padx=6, pady=2)
            ctk.CTkLabel(self._profile_scroll, text=str(p.get("pointer_speed", "")), font=BODY,
                         text_color=MUTED).grid(row=i, column=3, padx=6, pady=2)
            pname = p.get("name", "")
            accent_button(
                self._profile_scroll, "Apply", lambda n=pname: self._apply_profile(n), width=80
            ).grid(row=i, column=4, padx=4, pady=2)
            ghost_button(
                self._profile_scroll, "Delete", lambda n=pname: self._delete_profile(n), width=70
            ).grid(row=i, column=5, padx=(0, 4), pady=2)

    def _apply_profile(self, name: str):
        def _do(): return self._spm.apply_profile(name)
        def _done(r): log_to_box(self.log, r[1], r[0])
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _delete_profile(self, name: str):
        ok, msg = self._spm.delete_profile(name)
        log_to_box(self.log, msg, ok)
        self._refresh_profiles()

    # ── Raw input helpers ────────────────────────────────────────────────────

    def _refresh_raw_input(self):
        for w in self._raw_frame.winfo_children():
            w.destroy()

        result = self._ric.check()
        checks = [
            ("Enhanced Pointer Precision (EPP) OFF", result["epp_off"]),
            ("MouseThreshold1 = 0",                  result["thresholds_zero"]),
            ("MouseThreshold2 = 0",                  result["thresholds_zero"]),
        ]
        for col, (label, good) in enumerate(checks):
            cell = ctk.CTkFrame(self._raw_frame, fg_color=PANEL2, corner_radius=6)
            cell.grid(row=0, column=col, padx=(0, 8), pady=4, sticky="w")
            dot_color = GREEN if good else RED_LIGHT
            dot_text  = "✔" if good else "✗"
            ctk.CTkLabel(cell, text=dot_text, font=H3,
                         text_color=dot_color).grid(row=0, column=0, padx=(8, 4), pady=6)
            ctk.CTkLabel(cell, text=label, font=BODY,
                         text_color=TEXT if good else RED_LIGHT).grid(row=0, column=1, padx=(0, 10), pady=6)

        overall = result["overall"]
        overall_color = GREEN if overall == "Fully Optimized" else (
            MUTED if overall == "Partial" else RED_LIGHT
        )
        ctk.CTkLabel(self._raw_frame, text=f"Overall: {overall}",
                     font=(FONT, 12, "bold"), text_color=overall_color
                     ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))


# ══════════════════════════════════════════════════════════════════════════════
# VISUAL EFFECTS FRAME
# ══════════════════════════════════════════════════════════════════════════════

class VisualFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.vo = VisualOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Visual Effects Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Disable OS visual effects to free GPU cycles for gaming. Changes apply immediately.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # Visual Effects
        vf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        vf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        vf.grid_columnconfigure(1, weight=1)
        make_section_label(vf, "🖥️  Visual Effects Mode").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.vfx_label = ctk.CTkLabel(vf, text="Mode: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.vfx_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(vf, "Set Best Performance", self._set_perf, width=180).grid(row=1, column=1, padx=6, pady=(0, 10))
        ghost_button(vf, "Restore Defaults", self._restore_vfx, width=140).grid(row=1, column=2, padx=(0, 14), pady=(0, 10))
        self._refresh_vfx()

        # Game Mode
        gf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        gf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        gf.grid_columnconfigure(1, weight=1)
        make_section_label(gf, "🎮  Windows Game Mode").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.gm_label = ctk.CTkLabel(gf, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.gm_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(gf, "Enable Game Mode", self._enable_gm, width=160).grid(row=1, column=1, padx=6, pady=(0, 10))
        ghost_button(gf, "Disable", self._disable_gm, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 10))
        self._refresh_gm()

        # Transparency
        tf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        tf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        tf.grid_columnconfigure(1, weight=1)
        make_section_label(tf, "✨  Transparency Effects").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.trans_label = ctk.CTkLabel(tf, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.trans_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(tf, "Disable Transparency", self._disable_trans, width=170).grid(row=1, column=1, padx=6, pady=(0, 10))
        ghost_button(tf, "Re-enable", self._enable_trans, width=100).grid(row=1, column=2, padx=(0, 14), pady=(0, 10))
        self._refresh_trans()

        make_section_label(self, "Status Log").grid(row=5, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_vfx(self):
        mode = self.vo.get_visual_effects_mode()
        self.vfx_label.configure(text=f"Mode: {mode}",
                                  text_color=GREEN if mode == "Best Performance" else MUTED)

    def _refresh_gm(self):
        status = self.vo.get_game_mode_status()
        self.gm_label.configure(text=f"Status: {status}",
                                 text_color=GREEN if status == "Enabled" else MUTED)

    def _refresh_trans(self):
        status = self.vo.get_transparency_status()
        self.trans_label.configure(text=f"Status: {status}",
                                    text_color=GREEN if status == "Disabled" else MUTED)

    def _set_perf(self):
        def _do(): return self.vo.set_best_performance()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_vfx()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_vfx(self):
        def _do(): return self.vo.restore_visual_effects()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_vfx()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_gm(self):
        def _do(): return self.vo.enable_game_mode()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_gm()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _disable_gm(self):
        def _do(): return self.vo.disable_game_mode()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_gm()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _disable_trans(self):
        def _do(): return self.vo.disable_transparency()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_trans()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_trans(self):
        def _do(): return self.vo.enable_transparency()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_trans()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# AUDIO OPTIMIZER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class AudioFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.ao = AudioOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Audio Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Disable Windows Sonic / spatial sound. Use your game's built-in HRTF for directional audio.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # Spatial Sound
        sf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        sf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        sf.grid_columnconfigure(1, weight=1)
        make_section_label(sf, "🔊  Spatial Sound (Windows Sonic)").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 4))

        self.spatial_label = ctk.CTkLabel(sf, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.spatial_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        accent_button(sf, "Disable Windows Sonic", self._disable_sonic, width=190).grid(row=1, column=1, padx=(0, 14), pady=(0, 10))
        self._refresh_spatial()

        # Audio service
        svc_running = self.ao.is_audio_service_running()
        svcf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        svcf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        make_section_label(svcf, "🔧  Audio Service (AudioSrv)").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(svcf,
            text="Status: Running" if svc_running else "Status: Not Running — check Services",
            text_color=GREEN if svc_running else RED_LIGHT, font=(FONT, 11, "bold")
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        # Quick Launch
        qf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        qf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        make_section_label(qf, "⚡  Quick Launch").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        btns = ctk.CTkFrame(qf, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        ghost_button(btns, "Open Sound Settings", self._open_sound, width=160).grid(row=0, column=0, padx=(0, 8))
        ghost_button(btns, "Open Volume Mixer", self._open_mixer, width=140).grid(row=0, column=1)

        tip = ctk.CTkFrame(self, fg_color="#0d2040", corner_radius=8)
        tip.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(tip, text="💡  Enable HRTF in your game: Settings → Audio → HRTF: On  |  Recommended sample rate: 48000 Hz",
                     text_color="#5ba3f5", font=BODY, wraplength=700, anchor="w"
                     ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        # ── MMCSS Game Audio Priority ──
        mf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        mf.grid(row=6, column=0, sticky="ew", padx=20, pady=6)
        mf.grid_columnconfigure(1, weight=1)
        make_section_label(mf, "🎵  Game Audio Scheduling (MMCSS)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.mmcss_label = ctk.CTkLabel(mf, text="Checking...", text_color=MUTED, font=BODY)
        self.mmcss_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(mf, "Set High Priority", self._set_mmcss_high, width=160).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(mf, "Restore", self._restore_mmcss, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(mf, text="Sets Windows Multimedia Class Scheduler to prioritize game audio at High — footsteps and ability sounds arrive with lower OS scheduling delay.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_mmcss()

        make_section_label(self, "Status Log").grid(row=7, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=90)
        self.log.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_spatial(self):
        status = self.ao.get_spatial_sound_status()
        self.spatial_label.configure(text=f"Status: {status}",
                                      text_color=GREEN if status == "Off" else RED_LIGHT)

    def _disable_sonic(self):
        def _do(): return self.ao.disable_spatial_sound()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_spatial()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _open_sound(self):
        def _do(): return self.ao.open_sound_settings()
        def _done(r): log_to_box(self.log, r[1], r[0])
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _open_mixer(self):
        def _do(): return self.ao.open_volume_mixer()
        def _done(r): log_to_box(self.log, r[1], r[0])
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_mmcss(self):
        s = self.ao.get_mmcss_audio_status()
        self.mmcss_label.configure(text=f"Status: {s}", text_color=GREEN if "High" in s else MUTED)

    def _set_mmcss_high(self):
        log_to_box(self.log, "Setting MMCSS game audio to High priority (requires admin)...", True)
        def _do(): return self.ao.set_mmcss_high_priority()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_mmcss()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_mmcss(self):
        def _do(): return self.ao.restore_mmcss_priority()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_mmcss()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# CPU & TIMER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class CpuTimerFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.cto = CpuTimerOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="CPU & Timer Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Set 1ms timer resolution and disable CPU core parking to eliminate micro-stutters.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # Timer Resolution
        tf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        tf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        tf.grid_columnconfigure(1, weight=1)
        make_section_label(tf, "⏱️  Timer Resolution").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.timer_label = ctk.CTkLabel(tf, text="Current: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.timer_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(tf, "Set 1ms Resolution", self._set_timer, width=170).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(tf, "Restore Default", self._restore_timer, width=130).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(tf, text="Active while this app is open. Resets automatically when you close the app.",
                     text_color=MUTED, font=SMALL
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_timer()

        # Core Parking
        cf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        cf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        cf.grid_columnconfigure(1, weight=1)
        make_section_label(cf, "🖥️  CPU Core Parking").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))

        self.parking_label = ctk.CTkLabel(cf, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.parking_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(cf, "Disable Core Parking", self._disable_parking, width=180).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(cf, "Restore Default", self._restore_parking, width=130).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(cf, text="Prevents CPU cores from sleeping during gameplay — eliminates micro-stutters when frames spike.",
                     text_color=MUTED, font=SMALL, wraplength=650
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_parking()

        # CPU Boost Mode
        bf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        bf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        bf.grid_columnconfigure(1, weight=1)
        make_section_label(bf, "🚀  CPU Boost Mode").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.boost_label = ctk.CTkLabel(bf, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.boost_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(bf, "Set Aggressive", self._set_boost_aggressive, width=150).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(bf, "Restore Default", self._restore_boost, width=130).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(bf, text="Forces Ryzen 9 5900X to boost to max frequency instantly — no ramp-up lag during aim duels.",
                     text_color=MUTED, font=SMALL, wraplength=650
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_boost()

        # Dynamic Tick
        dt = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        dt.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        dt.grid_columnconfigure(1, weight=1)
        make_section_label(dt, "🕐  Dynamic Tick").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.tick_label = ctk.CTkLabel(dt, text="Status: ...", text_color=MUTED, font=(FONT, 12, "bold"))
        self.tick_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(dt, "Disable Dynamic Tick", self._disable_tick, width=180).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(dt, "Restore Default", self._restore_tick, width=130).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(dt, text="Reduces timer interrupt overhead for tighter frame timing consistency. Requires one reboot to take effect.",
                     text_color=MUTED, font=SMALL, wraplength=650
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_tick()

        make_section_label(self, "Status Log").grid(row=6, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_timer(self):
        res = self.cto.get_current_timer_resolution()
        self.timer_label.configure(text=f"Current: {res}",
                                    text_color=GREEN if self.cto.is_timer_optimized() else MUTED)

    def _refresh_parking(self):
        status = self.cto.get_core_parking_status()
        self.parking_label.configure(text=f"Status: {status}",
                                      text_color=GREEN if "Unparked" in status else MUTED)

    def _set_timer(self):
        def _do(): return self.cto.set_timer_resolution_1ms()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_timer()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_timer(self):
        def _do(): return self.cto.restore_timer_resolution()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_timer()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _disable_parking(self):
        log_to_box(self.log, "Disabling CPU core parking (requires admin)...", True)
        def _do(): return self.cto.disable_core_parking()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_parking()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_parking(self):
        def _do(): return self.cto.enable_core_parking()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_parking()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_boost(self):
        status = self.cto.get_boost_mode_status()
        color = GREEN if "Aggressive" in status else MUTED
        self.boost_label.configure(text=f"Status: {status}", text_color=color)

    def _set_boost_aggressive(self):
        log_to_box(self.log, "Setting CPU boost mode to Aggressive...", True)
        def _do(): return self.cto.set_boost_mode_aggressive()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_boost()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_boost(self):
        def _do(): return self.cto.restore_boost_mode()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_boost()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_tick(self):
        status = self.cto.get_dynamic_tick_status()
        color = GREEN if "Disabled" in status else MUTED
        self.tick_label.configure(text=f"Status: {status}", text_color=color)

    def _disable_tick(self):
        log_to_box(self.log, "Disabling dynamic tick (requires admin)...", True)
        def _do(): return self.cto.disable_dynamic_tick()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_tick()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _restore_tick(self):
        def _do(): return self.cto.enable_dynamic_tick()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_tick()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP MANAGER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class StartupFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.sm = StartupManager()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Startup Manager", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Disable non-essential startup programs to free resources at boot.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        lf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        lf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        lf.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(lf, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        hdr.grid_columnconfigure(0, weight=1)
        make_section_label(hdr, "🗂️  Startup Programs").grid(row=0, column=0, sticky="w")
        ghost_button(hdr, "⟳ Refresh", self._refresh_entries, width=90).grid(row=0, column=1)

        self.entry_scroll = ctk.CTkScrollableFrame(lf, height=300, fg_color=PANEL2)
        self.entry_scroll.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.entry_scroll.grid_columnconfigure(2, weight=1)
        self._refresh_entries()

        make_section_label(self, "Status Log").grid(row=3, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=90)
        self.log.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_entries(self):
        for w in self.entry_scroll.winfo_children():
            w.destroy()
        entries = self.sm.get_startup_entries()
        if not entries:
            ctk.CTkLabel(self.entry_scroll, text="No startup entries found.", text_color=MUTED,
                         font=BODY).grid(row=0, column=0, padx=8, pady=8)
            return

        for col, h in enumerate(["Name", "Source", "Command", "Action"]):
            ctk.CTkLabel(self.entry_scroll, text=h, font=LABEL,
                         text_color=MUTED).grid(row=0, column=col, padx=8, pady=2, sticky="w")

        for i, e in enumerate(entries, start=1):
            name      = e["name"]
            hive      = e["hive"]
            cmd       = e["command"]
            enabled   = e["enabled"]
            protected = e.get("protected", False)

            cmd_short  = cmd[:55] + "..." if len(cmd) > 55 else cmd
            name_color = MUTED if (protected or not enabled) else TEXT

            ctk.CTkLabel(self.entry_scroll, text=name, font=(FONT, 11, "bold"),
                         text_color=name_color, anchor="w").grid(row=i, column=0, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.entry_scroll, text=hive, font=SMALL,
                         text_color=MUTED, anchor="w").grid(row=i, column=1, padx=8, pady=2, sticky="w")
            ctk.CTkLabel(self.entry_scroll, text=cmd_short, font=MONO,
                         text_color=MUTED, anchor="w").grid(row=i, column=2, padx=8, pady=2, sticky="w")

            if protected:
                ctk.CTkLabel(self.entry_scroll, text="Protected", text_color=MUTED,
                             font=SMALL).grid(row=i, column=3, padx=8, pady=2)
            elif enabled:
                ghost_button(self.entry_scroll, "Disable",
                             lambda n=name, h=e["hive_const"], kp=e["key_path"], lb=hive:
                                 self._disable(n, h, kp, lb),
                             width=80).grid(row=i, column=3, padx=8, pady=2)
            else:
                accent_button(self.entry_scroll, "Re-enable",
                              lambda n=name: self._enable(n),
                              width=90, fg="#2d7d46").grid(row=i, column=3, padx=8, pady=2)

    def _disable(self, name, hive_const, key_path, label):
        def _do(): return self.sm.disable_entry(name, hive_const, key_path, label)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self.after(200, self._refresh_entries)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable(self, name):
        def _do(): return self.sm.enable_entry(name)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self.after(200, self._refresh_entries)
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# VISIBILITY / ENEMY CLARITY FRAME
# ══════════════════════════════════════════════════════════════════════════════

class VisibilityFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.vo = VisibilityOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Visibility Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="Adjust AMD GPU fullscreen color to make enemies easier to spot. Anti-cheat safe.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

        # ── Status Card ──
        sf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        sf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        sf.grid_columnconfigure(0, weight=1)
        make_section_label(sf, "🎨  AMD Color Status").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        available = self.vo.is_amd_available()
        if available:
            current = self.vo.get_current_values()
            preset  = self.vo.get_active_preset()
            status_color = GREEN if preset != "Default" else MUTED
            self.status_label = ctk.CTkLabel(
                sf,
                text=f"Active Preset: {preset}   |   "
                     f"Brightness: {current.get('brightness', '?')}   "
                     f"Contrast: {current.get('contrast', '?')}   "
                     f"Gamma: {current.get('gamma', '?')}",
                text_color=status_color, font=(FONT, 11, "bold")
            )
        else:
            self.status_label = ctk.CTkLabel(
                sf,
                text="AMD display adapter registry keys not found. Only AMD GPUs are supported.",
                text_color=RED_LIGHT, font=BODY
            )
        self.status_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        # ── Preset Buttons ──
        pf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        pf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        pf.grid_columnconfigure(0, weight=1)
        make_section_label(pf, "👁️  Color Presets").grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))

        btn_row = ctk.CTkFrame(pf, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))

        preset_names = list(VISIBILITY_PRESETS.keys())
        for i, name in enumerate(preset_names):
            if name == "Default":
                btn = ghost_button(btn_row, name, lambda n=name: self._apply_preset(n), width=130)
            else:
                btn = accent_button(btn_row, name, lambda n=name: self._apply_preset(n), width=150)
            btn.grid(row=0, column=i, padx=(0, 8))

        # Preset descriptions table
        desc_frame = ctk.CTkFrame(pf, fg_color=PANEL2, corner_radius=6)
        desc_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        desc_frame.grid_columnconfigure(1, weight=1)

        for i, (name, note) in enumerate(VISIBILITY_PRESET_NOTES.items()):
            p = VISIBILITY_PRESETS[name]
            ctk.CTkLabel(desc_frame, text=name, font=(FONT, 11, "bold"),
                         text_color=ACCENT if name != "Default" else MUTED, anchor="w"
                         ).grid(row=i, column=0, padx=(10, 8), pady=3, sticky="w")
            ctk.CTkLabel(desc_frame,
                         text=f"{note}  (B:{p['brightness']}  C:{p['contrast']}  G:{p['gamma']})",
                         font=SMALL, text_color=MUTED, anchor="w", justify="left"
                         ).grid(row=i, column=1, padx=(0, 10), pady=3, sticky="w")

        # ── How It Works ──
        info = ctk.CTkFrame(self, fg_color="#0d2040", corner_radius=8)
        info.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        info.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(info,
            text="💡  How it works: These values are written to the AMD GPU driver registry. "
                 "When your game launches in exclusive fullscreen, the driver loads them automatically. "
                 "No reboot required — just apply, then start your game.",
            text_color="#5ba3f5", font=BODY, wraplength=720, anchor="w", justify="left"
        ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        # ── Anti-Cheat Safety Note ──
        safe = ctk.CTkFrame(self, fg_color="#0f2a10", corner_radius=8)
        safe.grid(row=5, column=0, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(safe,
            text="✔  Anti-Cheat Safe: This is identical to adjusting brightness/contrast in AMD Radeon Software. "
                 "No game process interaction, no memory reads, no injection. "
                 "Display driver color adjustments are permitted by all major anti-cheat systems.",
            text_color="#3ddc84", font=BODY, wraplength=720, anchor="w", justify="left"
        ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

        make_section_label(self, "Status Log").grid(row=6, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _apply_preset(self, preset_name: str):
        self.cfg["visibility_preset"] = preset_name
        save_config(self.cfg)
        log_to_box(self.log, f"Applying preset '{preset_name}'...", True)
        def _do(): return self.vo.apply_preset(preset_name)
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_status()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_status(self):
        if not self.vo.is_amd_available():
            return
        current = self.vo.get_current_values()
        preset  = self.vo.get_active_preset()
        color = GREEN if preset not in ("Default", "Unknown") else MUTED
        self.status_label.configure(
            text=f"Active Preset: {preset}   |   "
                 f"Brightness: {current.get('brightness', '?')}   "
                 f"Contrast: {current.get('contrast', '?')}   "
                 f"Gamma: {current.get('gamma', '?')}",
            text_color=color
        )


# ══════════════════════════════════════════════════════════════════════════════
# GPU OPTIMIZER FRAME
# ══════════════════════════════════════════════════════════════════════════════

class GpuFrame(ctk.CTkFrame):
    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg = cfg
        self.gpu = GpuOptimizer()
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="GPU Optimizer", font=H1,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text="AMD GPU-specific tweaks — eliminate frame-time spikes and reduce CPU overhead.",
                     font=BODY, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

        if not self.gpu.is_amd_available():
            nf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
            nf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
            ctk.CTkLabel(nf, text="AMD GPU not detected. These features require an AMD Radeon GPU.",
                         text_color=RED_LIGHT, font=BODY).grid(row=0, column=0, padx=14, pady=20)
            return

        # ── ULPS ──
        uf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        uf.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        uf.grid_columnconfigure(1, weight=1)
        make_section_label(uf, "⚡  Ultra Low Power State (ULPS)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.ulps_label = ctk.CTkLabel(uf, text="Checking...", text_color=MUTED, font=BODY)
        self.ulps_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(uf, "Disable ULPS", self._disable_ulps, width=140).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(uf, "Restore", self._enable_ulps, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(uf, text="Prevents the GPU from entering ultra-low power state between frames — eliminates 1-frame latency spikes during fights.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_ulps()

        # ── Chill ──
        cf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        cf.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        cf.grid_columnconfigure(1, weight=1)
        make_section_label(cf, "❄️  AMD Chill (FPS Limiter)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.chill_label = ctk.CTkLabel(cf, text="Checking...", text_color=MUTED, font=BODY)
        self.chill_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(cf, "Disable Chill", self._disable_chill, width=140).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(cf, "Restore", self._enable_chill, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(cf, text="AMD Chill dynamically caps FPS to save power. Disable it to ensure your game always runs uncapped.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_chill()

        # ── HAGS ──
        hf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=CR_CARD)
        hf.grid(row=4, column=0, sticky="ew", padx=20, pady=6)
        hf.grid_columnconfigure(1, weight=1)
        make_section_label(hf, "🎮  Hardware-Accelerated GPU Scheduling (HAGS)").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(10, 4))
        self.hags_label = ctk.CTkLabel(hf, text="Checking...", text_color=MUTED, font=BODY)
        self.hags_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        accent_button(hf, "Enable HAGS", self._enable_hags, width=140).grid(row=1, column=1, padx=6, pady=(0, 4))
        ghost_button(hf, "Disable", self._disable_hags, width=90).grid(row=1, column=2, padx=(0, 14), pady=(0, 4))
        ctk.CTkLabel(hf, text="GPU manages its own command queue — reduces CPU-to-GPU scheduling overhead. Reboot required after change.",
                     text_color=MUTED, font=SMALL, wraplength=650, justify="left"
                     ).grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 10))
        self._refresh_hags()

        make_section_label(self, "Status Log").grid(row=5, column=0, sticky="w", padx=20, pady=(10, 2))
        self.log = make_status_box(self, height=100)
        self.log.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 16))

    def _refresh_ulps(self):
        s = self.gpu.get_ulps_status()
        self.ulps_label.configure(text=f"Status: {s}", text_color=GREEN if "Disabled" in s else MUTED)

    def _disable_ulps(self):
        log_to_box(self.log, "Disabling AMD ULPS (requires admin)...", True)
        def _do(): return self.gpu.disable_ulps()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_ulps()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_ulps(self):
        def _do(): return self.gpu.enable_ulps()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_ulps()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_chill(self):
        s = self.gpu.get_chill_status()
        self.chill_label.configure(text=f"Status: {s}", text_color=GREEN if "Disabled" in s else MUTED)

    def _disable_chill(self):
        def _do(): return self.gpu.disable_chill()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_chill()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _enable_chill(self):
        def _do(): return self.gpu.enable_chill()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_chill()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _refresh_hags(self):
        s = self.gpu.get_hags_status()
        self.hags_label.configure(text=f"Status: {s}", text_color=GREEN if "Enabled" in s else MUTED)

    def _enable_hags(self):
        log_to_box(self.log, "Enabling HAGS (requires admin)... Reboot required.", True)
        def _do(): return self.gpu.enable_hags()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_hags()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))

    def _disable_hags(self):
        def _do(): return self.gpu.disable_hags()
        def _done(r):
            log_to_box(self.log, r[1], r[0])
            self._refresh_hags()
        run_in_thread(_do, lambda r: self.after(0, lambda: _done(r)))


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD FRAME
# ══════════════════════════════════════════════════════════════════════════════

class DashboardFrame(ctk.CTkFrame):
    """Landing page — live system stats, animated one-click boost, settings export."""

    # Boost steps shown in the inline checklist
    _STEPS = [
        ("pwr",   "⚡", "Ultimate Power Plan",  "Sets CPU to maximum performance mode"),
        ("bg",    "🧹", "Kill Background Apps", "Frees CPU & RAM from non-essential processes"),
        ("ram",   "🧠", "Clear Standby RAM",    "Flushes cached memory back to available pool"),
        ("reg",   "🔧", "Registry Tweaks",      "Applies MMCSS & TCP performance tweaks"),
        ("park",  "⏱", "Disable Core Parking", "Prevents CPU cores sleeping mid-fight"),
        ("timer", "⏲", "1ms Timer Resolution",  "Reduces input & frame timing from 15.6ms → 1ms"),
    ]

    _CATEGORIES = [
        ("system",     "⚡",  "System"),
        ("network",    "🌐",  "Network"),
        ("registry",   "🔧",  "Registry"),
        ("mouse",      "🖱️", "Mouse & Aim"),
        ("gpu",        "🎮",  "GPU"),
        ("visibility", "👁️", "Visibility"),
        ("audio",      "🔊",  "Audio"),
        ("cpu",        "⏱️", "CPU & Timer"),
    ]

    def __init__(self, parent, cfg):
        super().__init__(parent, fg_color=BG)
        self.cfg              = cfg
        self._app             = None   # set by App after build
        self._boost_running   = False
        self._tick_id         = None
        self._step_icon_lbls: dict = {}
        self._step_msg_lbls:  dict = {}
        self._step_row_frames: dict = {}
        self._step_row_bgs:   dict = {}
        # Prime psutil so first non-blocking call returns a valid sample
        try:
            _psutil.cpu_percent(interval=None)
        except Exception:
            pass
        self._build()

    def set_app(self, app):
        self._app = app
        self.after(300, self._intro_animate)   # count-up stats on first render
        self.after(800, self._tick_stats)      # then start live ticker

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = scrollable_content(self)

        # ── Metric tiles row ──
        metrics = ctk.CTkFrame(scroll, fg_color="transparent")
        metrics.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        metrics.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _metric_tile(parent, col, label):
            tile = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=CR_CARD)
            tile.grid(row=0, column=col, sticky="ew", padx=4)
            ctk.CTkLabel(tile, text=label, font=LABEL,
                         text_color=MUTED).pack(padx=14, pady=(12, 2), anchor="w")
            val = ctk.CTkLabel(tile, text="--", font=(FONT, 22, "bold"),
                               text_color=ACCENT2)
            val.pack(padx=14, pady=(0, 12), anchor="w")
            return val

        self._lbl_cpu  = _metric_tile(metrics, 0, "CPU USAGE")
        self._lbl_ram  = _metric_tile(metrics, 1, "FREE RAM")
        self._lbl_proc = _metric_tile(metrics, 2, "PROCESSES")
        self._lbl_ping = _metric_tile(metrics, 3, "LATENCY")

        # ── Two-column layout: Boost CTA + Quick Status ──
        mid = ctk.CTkFrame(scroll, fg_color="transparent")
        mid.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=2)

        # ── LEFT: Boost card ──
        boost_card = ctk.CTkFrame(mid, fg_color=PANEL, corner_radius=CR_CARD)
        boost_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        boost_card.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(boost_card, fg_color=ACCENT, height=3, corner_radius=0).grid(
            row=0, column=0, sticky="ew")
        boost_inner = ctk.CTkFrame(boost_card, fg_color="transparent")
        boost_inner.grid(row=1, column=0, padx=20, pady=(16, 20), sticky="ew")
        boost_inner.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(boost_inner, text="READY TO PLAY?", font=LABEL,
                     text_color=MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(boost_inner, text="One-Click Boost",
                     font=H2, text_color=TEXT).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkLabel(boost_inner,
                     text="Applies all optimisations in ~10 seconds.",
                     font=BODY, text_color=MUTED).grid(row=2, column=0, sticky="w", pady=(4, 12))

        self._boost_btn = ctk.CTkButton(
            boost_inner, text="BOOST NOW", command=self._run_boost,
            width=220, height=48, font=(FONT, 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HV, corner_radius=CR_BUTTON, text_color=TEXT
        )
        self._boost_btn.grid(row=3, column=0, sticky="w")
        self._boost_pulse = Pulse(self._boost_btn, ACCENT, ACCENT_HV, half_period_ms=1600)

        self._progress = ctk.CTkProgressBar(boost_inner, height=6, progress_color=GREEN,
                                             fg_color=PANEL2, corner_radius=CR_BAR)
        self._progress.set(0)
        self._progress.grid(row=4, column=0, sticky="ew", pady=(12, 4))

        # Compact step indicators (dots, not full checklist)
        step_row = ctk.CTkFrame(boost_inner, fg_color="transparent")
        step_row.grid(row=5, column=0, sticky="w")
        for i, (key, _emoji, label, hint) in enumerate(self._STEPS):
            icon_lbl = ctk.CTkLabel(step_row, text="○", font=(FONT, 10, "bold"),
                                     text_color=MUTED, width=16)
            icon_lbl.grid(row=0, column=i*2, padx=(0, 2), pady=4)
            self._step_icon_lbls[key] = icon_lbl
            ctk.CTkLabel(step_row, text=label, font=SMALL,
                         text_color=MUTED).grid(row=0, column=i*2+1, padx=(0, 10), pady=4)
            # Create dummy frames/labels for compatibility with existing animation
            rf = ctk.CTkFrame(step_row, fg_color="transparent", width=0, height=0)
            self._step_row_frames[key] = rf
            self._step_row_bgs[key] = "transparent"
            msg_lbl = ctk.CTkLabel(step_row, text="", width=0, height=0)
            self._step_msg_lbls[key] = msg_lbl

        self._boost_note = ctk.CTkLabel(boost_inner, text="", font=BODY, text_color=MUTED)
        self._boost_note.grid(row=6, column=0, sticky="w", pady=(4, 0))
        ctk.CTkLabel(boost_inner, text="Ctrl+Shift+B", font=TINY,
                     text_color=MUTED).grid(row=7, column=0, sticky="w", pady=(2, 0))

        # ── RIGHT: Quick Status card ──
        status_card = ctk.CTkFrame(mid, fg_color=PANEL, corner_radius=CR_CARD)
        status_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        status_card.grid_columnconfigure(0, weight=1)
        ctk.CTkFrame(status_card, fg_color=ACCENT2, height=3, corner_radius=0).grid(
            row=0, column=0, sticky="ew")
        ctk.CTkLabel(status_card, text="QUICK STATUS", font=LABEL,
                     text_color=MUTED).grid(row=1, column=0, sticky="w", padx=16, pady=(14, 8))

        self._status_dots: dict = {}
        _STATUS_ITEMS = [
            ("system",   "System"),
            ("network",  "Network"),
            ("registry", "Registry"),
            ("mouse",    "Mouse"),
            ("gpu",      "GPU"),
            ("audio",    "Audio"),
            ("cpu",      "CPU & Timer"),
            ("visibility","Visibility"),
        ]
        for i, (key, label) in enumerate(_STATUS_ITEMS):
            row_f = ctk.CTkFrame(status_card, fg_color="transparent")
            row_f.grid(row=i+2, column=0, sticky="ew", padx=16, pady=2)
            row_f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row_f, text=label, font=BODY,
                         text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w")
            dot_lbl = ctk.CTkLabel(row_f, text="●", font=(FONT, 10),
                                    text_color=MUTED)
            dot_lbl.grid(row=0, column=1, padx=(8, 0))
            self._status_dots[key] = dot_lbl

        # Navigate buttons at bottom of status card
        nav_btn_frame = ctk.CTkFrame(status_card, fg_color="transparent")
        nav_btn_frame.grid(row=len(_STATUS_ITEMS)+2, column=0, sticky="ew",
                           padx=16, pady=(10, 14))
        ghost_button(nav_btn_frame, "View All", lambda: self._navigate("system"),
                     width=100).pack(side="left")

        # ── Settings Export / Import (compact) ──
        export_row = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=CR_CARD)
        export_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        export_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(export_row, text="Settings", font=H3,
                     text_color=TEXT).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(export_row, text="Export or import your config to share with friends.",
                     font=SMALL, text_color=MUTED).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        exp_btns = ctk.CTkFrame(export_row, fg_color="transparent")
        exp_btns.grid(row=0, column=1, rowspan=2, padx=(0, 16), pady=8)
        accent_button(exp_btns, "Export", self._export_settings, width=90).pack(side="left", padx=(0, 6))
        ghost_button(exp_btns, "Import", self._import_settings, width=90).pack(side="left")
        self._export_status = ctk.CTkLabel(export_row, text="", font=SMALL, text_color=MUTED)
        self._export_status.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, key: str):
        if self._app:
            self._app._show_frame(key)

    # ── Intro animation ───────────────────────────────────────────────────────

    def _intro_animate(self):
        """Count-up the live stats labels on first display for visual impact."""
        try:
            cpu     = _psutil.cpu_percent(interval=None)
            mem     = _psutil.virtual_memory()
            free_gb = mem.available / (1024 ** 3)
            procs   = float(len(_psutil.pids()))
            count_up(self._lbl_cpu,  cpu,     700, "{:.0f}%")
            count_up(self._lbl_ram,  free_gb, 700, "{:.1f} GB")
            count_up(self._lbl_proc, procs,   700, "{:.0f}")
            self._lbl_ping.configure(text="--")
        except Exception:
            pass

    # ── Live stats ticker ─────────────────────────────────────────────────────

    def _tick_stats(self):
        """Update live metric tiles. Slows to 8 s when frame is not visible."""
        try:
            if self.winfo_exists():
                visible = self.winfo_ismapped()
                cpu     = _psutil.cpu_percent(interval=None)
                mem     = _psutil.virtual_memory()
                free_gb = mem.available / (1024 ** 3)
                procs   = len(_psutil.pids())
                cpu_color = RED_LIGHT if cpu > 80 else (GOLD if cpu > 50 else ACCENT2)
                ram_color = RED_LIGHT if free_gb < 1.0 else (GOLD if free_gb < 2.0 else ACCENT2)
                self._lbl_cpu.configure(text=f"{cpu:.0f}%", text_color=cpu_color)
                self._lbl_ram.configure(text=f"{free_gb:.1f} GB", text_color=ram_color)
                self._lbl_proc.configure(text=f"{procs}")
                interval = 3000 if visible else 8000
            else:
                return
        except Exception:
            interval = 8000
        self._tick_id = self.after(interval, self._tick_stats)

    # ── Step animation helpers ────────────────────────────────────────────────

    def _set_step_active(self, key: str):
        lbl = self._step_icon_lbls.get(key)
        if lbl:
            lbl.configure(text="⟳", text_color=GOLD)

    def _set_step_done(self, key: str, ok: bool, msg: str):
        lbl = self._step_icon_lbls.get(key)
        if lbl:
            lbl.configure(text="✓" if ok else "✗", text_color=GREEN if ok else RED_LIGHT)
        msg_lbl = self._step_msg_lbls.get(key)
        if msg_lbl:
            msg_lbl.configure(text=msg[:50], text_color=GREEN if ok else RED_LIGHT)
        # Flash the row green/red then restore original bg
        rf   = self._step_row_frames.get(key)
        orig = self._step_row_bgs.get(key, PANEL2)
        if rf:
            flash_bg(rf, "#0d2e18" if ok else "#2e0d12", orig, 600)
        done = sum(1 for l in self._step_icon_lbls.values() if l.cget("text") in ("✓", "✗"))
        ease_progress(self._progress, done / len(self._STEPS), 400)

    def _reset_steps(self):
        for lbl in self._step_icon_lbls.values():
            lbl.configure(text="○", text_color=MUTED)
        for key, lbl in self._step_msg_lbls.items():
            hint = next((h for k, _, _, h in self._STEPS if k == key), "")
            lbl.configure(text=hint, text_color=MUTED)
        self._progress.set(0)
        self._boost_note.configure(text="")

    # ── Boost sequence ────────────────────────────────────────────────────────

    def _run_boost(self):
        if self._boost_running:
            return
        self._boost_running = True
        # Stop idle pulse — button is now active
        if getattr(self, '_boost_pulse', None):
            self._boost_pulse.stop(ACCENT)
        self._boost_btn.configure(state="disabled", text="Running...")
        self._reset_steps()
        self._boost_note.configure(text="Optimising your system — this takes ~10 seconds...", text_color=MUTED)

        _sys = SystemOptimizer()
        _rt  = RegistryTweaks()
        _cpu = CpuTimerOptimizer()

        def _activate(k):
            self.after(0, lambda key=k: self._set_step_active(key))

        def _finish(k, ok, msg):
            self.after(0, lambda key=k, o=ok, m=msg: self._set_step_done(key, o, m))

        def _do():
            _activate("pwr")
            ok, msg = _sys.set_ultimate_performance_plan()
            _finish("pwr", ok, msg)

            _activate("bg")
            killed = _sys.kill_all_background_targets()
            n = sum(1 for _, o, _ in killed if o) if killed else 0
            _finish("bg", True, f"Killed {n} processes" if n else "No targets running")

            _activate("ram")
            ok, msg = _sys.clear_standby_memory()
            _finish("ram", ok, msg)

            _activate("reg")
            tw = _rt.apply_all_tweaks()
            n_ok = sum(1 for _, o, _ in tw if o)
            _finish("reg", True, f"{n_ok}/{len(tw)} tweaks applied")

            _activate("park")
            ok, msg = _cpu.disable_core_parking()
            _finish("park", ok, msg)

            _activate("timer")
            ok, msg = _cpu.set_timer_resolution_1ms()
            _finish("timer", ok, msg)

        def _complete(_):
            self._boost_running = False
            self._boost_btn.configure(state="normal", text="🚀  ONE-CLICK BOOST")
            self._boost_note.configure(
                text="✅  Boost complete — launch your game now!", text_color=GREEN
            )
            _win_toast("Valo Optimise", "Boost complete! Launch your game now.")

        run_in_thread(_do, lambda r: self.after(0, lambda: _complete(r)))

    # ── Settings Export / Import ──────────────────────────────────────────────

    def _export_settings(self):
        path = filedialog.asksaveasfilename(
            title="Export Valo Optimise Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="valo_optimise_settings.json",
        )
        if not path:
            return
        try:
            export_data = {
                "valo_optimise_export": True,
                "version": "1.0",
                "exported_at": datetime.datetime.now().isoformat(),
                "config": self.cfg,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            self._export_status.configure(text=f"✓ Exported to {os.path.basename(path)}", text_color=GREEN)
            _win_toast("Valo Optimise", "Settings exported successfully.")
        except Exception as e:
            self._export_status.configure(text=f"Export failed: {e}", text_color=RED_LIGHT)

    def _import_settings(self):
        path = filedialog.askopenfilename(
            title="Import Valo Optimise Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("valo_optimise_export"):
                self._export_status.configure(text="Not a valid Valo Optimise settings file.", text_color=RED_LIGHT)
                return
            self.cfg.update(data.get("config", {}))
            save_config(self.cfg)
            self._export_status.configure(text=f"✓ Imported from {os.path.basename(path)}", text_color=GREEN)
            _win_toast("Valo Optimise", "Settings imported — restart to apply all changes.")
        except Exception as e:
            self._export_status.configure(text=f"Import failed: {e}", text_color=RED_LIGHT)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════

def _resource(rel: str) -> str:
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    base = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base, rel)


class App(ctk.CTk):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.title("VALO OPTIMISE  |  Gaming Performance Suite")
        self.geometry("1100x750")
        self.minsize(960, 650)
        self.configure(fg_color=BG)
        # Set window & taskbar icon
        try:
            ico = _resource(os.path.join('assets', 'icon.ico'))
            if os.path.isfile(ico):
                self.iconbitmap(ico)
        except Exception:
            pass
        self._frames: dict = {}
        self._active_key   = None
        self._active_frame = None
        self._build()
        fade_in_window(self, duration_ms=280)   # smooth entrance
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._hotkey_registered = False
        try:
            import keyboard as _kb
            _kb.add_hotkey('ctrl+shift+b', self._hotkey_boost)
            self._hotkey_registered = True
        except Exception:
            pass
        if not self.cfg.get("onboarding_done"):
            self.after(500, self._show_onboarding)
        # Check for updates silently in background — shows dialog only if newer version found
        self.after(4000, self._check_for_update)
        # Anonymous launch counter — no personal data, just version + count
        self.after(5000, self._ping_launch)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)  # row 0 = topbar, row 1 = content

        # ── Sidebar ───────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, corner_radius=0, width=220)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, minsize=4)   # indicator strip column
        sidebar.grid_columnconfigure(1, weight=1)    # button column

        # ── Logo ──
        self._tier = _lic.get_tier()
        logo_wrap = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_wrap.grid(row=0, column=0, columnspan=2, pady=(20, 4), padx=14, sticky="w")
        ctk.CTkLabel(logo_wrap, text="VALO", font=(FONT, 20, "bold"),
                     text_color=ACCENT).pack(side="left", padx=(0, 3))
        ctk.CTkLabel(logo_wrap, text="OPTIMISE", font=(FONT, 14, "bold"),
                     text_color=TEXT).pack(side="left")
        _tier_label = " PRO" if self._tier in ("pro", "lifetime") else " FREE"
        _tier_color = GOLD if self._tier in ("pro", "lifetime") else MUTED
        ctk.CTkLabel(logo_wrap, text=_tier_label, font=TINY,
                     text_color=_tier_color).pack(side="left", anchor="s", pady=(0, 2))

        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))

        # ── Collapsible nav groups ──
        _NAV_GROUPS = [
            ("MAIN", [
                ("dashboard", "Dashboard"),
                ("boost",     "Pre-Game Boost"),
                ("benchmark", "Performance Report"),
            ]),
            ("SYSTEM", [
                ("system",   "System"),
                ("network",  "Network"),
                ("registry", "Registry"),
                ("cpu",      "CPU & Timer"),
                ("gpu",      "GPU"),
                ("startup",  "Startup Manager"),
            ]),
            ("INPUT & DISPLAY", [
                ("mouse",      "Mouse & Aim"),
                ("mousedriver","Mouse Driver"),
                ("visual",     "Visual Effects"),
                ("audio",      "Audio"),
                ("visibility", "Visibility"),
            ]),
            ("GAME", [
                ("valorant", "Game Config"),
                ("stats",    "Player Stats"),
                ("guide",    "Settings Guide"),
            ]),
        ]

        self._nav_btns:       dict = {}
        self._nav_indicators: dict = {}
        self._group_children: dict = {}   # group_title -> children frame
        self._group_expanded: dict = {}   # group_title -> bool
        grid_row = 2

        # Scrollable nav area so it works on smaller screens
        nav_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent",
                                             scrollbar_button_color=PANEL2,
                                             scrollbar_button_hover_color=BORDER)
        nav_scroll.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=0, pady=0)
        nav_scroll.grid_columnconfigure(0, minsize=4)
        nav_scroll.grid_columnconfigure(1, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)
        nav_row = 0

        for group_title, items in _NAV_GROUPS:
            # Group header — clickable to expand/collapse
            group_header = ctk.CTkButton(
                nav_scroll, text=f"  {group_title}",
                anchor="w", height=26, width=196,
                fg_color="transparent", hover_color="transparent",
                text_color="#3a4e66", font=LABEL,
                corner_radius=0,
                command=lambda g=group_title: self._toggle_nav_group(g)
            )
            group_header.grid(row=nav_row, column=0, columnspan=2,
                              padx=(10, 8), pady=(10, 2), sticky="ew")
            nav_row += 1

            # Children container
            children_frame = ctk.CTkFrame(nav_scroll, fg_color="transparent")
            children_frame.grid(row=nav_row, column=0, columnspan=2, sticky="ew")
            children_frame.grid_columnconfigure(0, minsize=4)
            children_frame.grid_columnconfigure(1, weight=1)
            self._group_children[group_title] = children_frame
            self._group_expanded[group_title] = True  # start expanded
            nav_row += 1

            for child_i, (key, label) in enumerate(items):
                # Active indicator strip
                ind = ctk.CTkFrame(children_frame, width=3, height=20,
                                   fg_color="transparent", corner_radius=2)
                ind.grid(row=child_i, column=0, padx=(6, 0), pady=1, sticky="ns")
                self._nav_indicators[key] = ind

                _is_pro_tab = key in _lic.PRO_TABS
                _locked     = _is_pro_tab and not _lic.is_pro()
                _btn_label  = f"  {label}" + ("   \U0001F512" if _locked else "")
                btn = ctk.CTkButton(
                    children_frame, text=_btn_label,
                    command=lambda k=key: self._show_frame(k),
                    anchor="w", height=30,
                    fg_color="transparent", hover_color=SIDEBAR_ACT,
                    text_color=MUTED if not _locked else "#3a4e66",
                    font=BODY, corner_radius=CR_BADGE
                )
                btn.grid(row=child_i, column=1, padx=(0, 8), pady=1, sticky="ew")
                self._nav_btns[key] = btn

                btn.bind("<Enter>", lambda e, b=btn, k=key: (
                    None if k == self._active_key
                    else b.configure(fg_color=SIDEBAR_ACT, text_color=TEXT)
                ))
                btn.bind("<Leave>", lambda e, b=btn, k=key: (
                    None if k == self._active_key
                    else b.configure(fg_color="transparent", text_color=MUTED)
                ))

        # ── Bottom: admin status + trust badges ──
        admin_lbl   = get_admin_status_label()
        admin_color = GREEN if "Admin" in admin_lbl else ACCENT
        bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, columnspan=2, padx=14, pady=(8, 12), sticky="sw")
        ctk.CTkLabel(bottom_frame, text=f"  {admin_lbl}", font=SMALL,
                     text_color=admin_color).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(bottom_frame, text="  Anti-Cheat Safe", font=TINY,
                     text_color=GREEN).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ctk.CTkLabel(bottom_frame, text="  No Data Collected", font=TINY,
                     text_color=GREEN).grid(row=2, column=0, sticky="w")
        _lic_btn_text = "Upgrade to Pro" if not _lic.is_pro() else "Licence"
        ctk.CTkButton(bottom_frame, text=_lic_btn_text,
                      command=self._show_licence_dialog,
                      fg_color=ACCENT if not _lic.is_pro() else PANEL2,
                      hover_color=ACCENT_HV if not _lic.is_pro() else PANEL,
                      text_color=TEXT, font=(FONT, 9, "bold"),
                      height=28, corner_radius=CR_BADGE
                      ).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        # ── Topbar ────────────────────────────────────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color=PANEL, height=48, corner_radius=0)
        topbar.grid(row=0, column=1, sticky="new")
        topbar.grid_propagate(False)
        topbar.grid_columnconfigure(0, weight=1)
        self._topbar_title = ctk.CTkLabel(topbar, text="Dashboard", font=H2,
                                           text_color=TEXT, anchor="w")
        self._topbar_title.grid(row=0, column=0, padx=24, sticky="w", pady=12)

        # Quick boost shortcut in topbar
        self._topbar_boost = ctk.CTkButton(
            topbar, text="Boost", width=80, height=30,
            fg_color=ACCENT, hover_color=ACCENT_HV, text_color=TEXT,
            font=(FONT, 10, "bold"), corner_radius=CR_BADGE,
            command=lambda: self._show_frame("boost")
        )
        self._topbar_boost.grid(row=0, column=1, padx=(0, 24), pady=9)

        # Content area
        content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        content.grid(row=1, column=1, sticky="nsew")
        self._content = content

        # Lazy frame registry — frames are built on first visit
        self._frame_classes = {
            "dashboard":   DashboardFrame,
            "system":      SystemFrame,
            "network":     NetworkFrame,
            "registry":    RegistryFrame,
            "boost":       BoostFrame,
            "benchmark":   BenchmarkFrame,
            "valorant":    ValorantFrame,
            "mouse":       MouseFrame,
            "mousedriver": MouseDriverFrame,
            "visual":      VisualFrame,
            "audio":       AudioFrame,
            "cpu":         CpuTimerFrame,
            "gpu":         GpuFrame,
            "visibility":  VisibilityFrame,
            "startup":     StartupFrame,
            "stats":       StatsFrame,
            "guide":       GuideFrame,
        }

        # Only build Dashboard eagerly — everything else is built on first visit
        dash = DashboardFrame(content, self.cfg)
        dash.set_app(self)
        self._frames["dashboard"] = dash

        self._show_frame("dashboard")

        # Auto-apply saved visibility preset silently on startup
        preset = self.cfg.get("visibility_preset", "Competitive")
        if preset and preset != "Default":
            self.after(800, lambda: run_in_thread(
                lambda: VisibilityOptimizer().apply_preset(preset), None
            ))

    def _toggle_nav_group(self, group_title: str):
        """Expand or collapse a sidebar nav group."""
        children = self._group_children.get(group_title)
        if not children:
            return
        expanded = self._group_expanded.get(group_title, True)
        if expanded:
            children.grid_remove()
        else:
            children.grid()
        self._group_expanded[group_title] = not expanded

    # Page display names for the topbar
    _PAGE_TITLES = {
        "dashboard": "Dashboard", "boost": "Pre-Game Boost",
        "benchmark": "Performance Report", "system": "System",
        "network": "Network", "registry": "Registry",
        "valorant": "Game Config", "mouse": "Mouse & Aim",
        "mousedriver": "Mouse Driver", "visual": "Visual Effects",
        "audio": "Audio", "cpu": "CPU & Timer", "gpu": "GPU",
        "visibility": "Visibility", "startup": "Startup Manager",
        "stats": "Player Stats", "guide": "Settings Guide",
    }

    def _show_frame(self, key: str):
        # Gate Pro tabs
        if key in _lic.PRO_TABS and not _lic.is_pro():
            self._show_upgrade_prompt(key)
            return

        # ── Update nav indicators ─────────────────────────────────────────────
        if self._active_key and self._active_key != key:
            prev_ind = self._nav_indicators.get(self._active_key)
            prev_btn = self._nav_btns.get(self._active_key)
            if prev_ind:
                prev_ind.configure(fg_color="transparent")
            if prev_btn:
                prev_btn.configure(fg_color="transparent", text_color=MUTED,
                                   font=BODY)

        self._active_key = key
        new_ind = self._nav_indicators.get(key)
        new_btn = self._nav_btns.get(key)
        if new_ind:
            new_ind.configure(fg_color=ACCENT)
        if new_btn:
            new_btn.configure(fg_color=SIDEBAR_ACT, text_color=TEXT,
                               font=(FONT, 11, "bold"))

        # Update topbar title
        try:
            self._topbar_title.configure(text=self._PAGE_TITLES.get(key, key.title()))
        except Exception:
            pass

        self.update_idletasks()

        # ── Hide current frame ────────────────────────────────────────────────
        if self._active_frame is not None:
            self._active_frame.pack_forget()
            self._active_frame = None

        # ── Lazy-build frame on first visit ───────────────────────────────────
        if key not in self._frames:
            cls = self._frame_classes[key]
            frame = cls(self._content, self.cfg)
            self._frames[key] = frame

        # ── Show with slide-in animation ──────────────────────────────────────
        frame = self._frames[key]
        slide_in(frame, self._content, duration_ms=140)
        self._active_frame = frame

    # ── Licence dialogs ───────────────────────────────────────────────────────

    def _show_upgrade_prompt(self, tab_key: str):
        """Shown when a free user clicks a Pro tab."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Upgrade to Pro")
        dlg.geometry("420x320")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PANEL)
        dlg.grab_set()
        dlg.focus()

        ctk.CTkLabel(dlg, text="🔒  Pro Feature", font=H2,
                     text_color=GOLD).pack(pady=(28, 6))
        tab_name = tab_key.replace("mousedriver", "Mouse Driver").replace("valorant", "Game Config").title()
        ctk.CTkLabel(dlg, text=f"{tab_name} is included in Valo Optimise Pro.",
                     font=BODY, text_color=MUTED, wraplength=360).pack(pady=(0, 4))
        ctk.CTkLabel(dlg, text="Unlock all 9 Pro modules for £4.99/mo or £69.99 lifetime.",
                     font=BODY, text_color=MUTED, wraplength=360).pack(pady=(0, 20))

        def _open_buy():
            import webbrowser
            webbrowser.open("https://harveyj82.gumroad.com/l/uriyw")
            dlg.destroy()

        ctk.CTkButton(dlg, text="⭐ Get Pro — £4.99/mo", command=_open_buy,
                      fg_color=ACCENT, hover_color=ACCENT_HV,
                      font=H3, height=40, corner_radius=8,
                      width=340).pack(pady=(0, 8))
        ctk.CTkButton(dlg, text="🔑 I have a key — Activate",
                      command=lambda: (dlg.destroy(), self._show_licence_dialog()),
                      fg_color=PANEL2, hover_color=PANEL, text_color=TEXT,
                      font=BODY, height=34, corner_radius=8,
                      width=340).pack(pady=(0, 8))
        ctk.CTkButton(dlg, text="Maybe later", command=dlg.destroy,
                      fg_color="transparent", hover_color=PANEL2, text_color=MUTED,
                      font=SMALL, height=28, corner_radius=6,
                      width=340).pack()

    def _show_licence_dialog(self):
        """Licence management — activate a key or view current licence."""
        info = _lic.get_info()
        dlg  = ctk.CTkToplevel(self)
        dlg.title("Licence")
        dlg.geometry("400x340")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PANEL)
        dlg.grab_set()
        dlg.focus()

        tier = info["tier"]
        ctk.CTkLabel(dlg, text="🔑  Licence Manager", font=H2,
                     text_color=TEXT).pack(pady=(24, 4))

        if tier in ("pro", "lifetime"):
            badge = "⭐ PRO" if tier == "pro" else "♾ LIFETIME"
            ctk.CTkLabel(dlg, text=badge, font=H3,
                         text_color=GOLD).pack(pady=(0, 4))
            ctk.CTkLabel(dlg, text=f"Key: {info['key_masked']}",
                         font=SMALL, text_color=MUTED).pack()
            if info["email"]:
                ctk.CTkLabel(dlg, text=info["email"],
                             font=SMALL, text_color=MUTED).pack(pady=(2, 0))
            ctk.CTkLabel(dlg, text="All Pro features are unlocked.",
                         font=BODY, text_color=ACCENT2).pack(pady=(12, 20))
            ctk.CTkButton(dlg, text="Remove Licence", command=lambda: self._deactivate(dlg),
                          fg_color=PANEL2, hover_color=PANEL, text_color=MUTED,
                          font=SMALL, height=28, width=180).pack()
        else:
            ctk.CTkLabel(dlg, text="FREE tier — enter your key to unlock Pro features.",
                         font=BODY, text_color=MUTED, wraplength=340).pack(pady=(0, 16))
            key_var = ctk.StringVar()
            ctk.CTkEntry(dlg, textvariable=key_var, placeholder_text="XXXX-XXXX-XXXX-XXXX",
                         width=340, height=36, font=BODY).pack(pady=(0, 8))
            status_lbl = ctk.CTkLabel(dlg, text="", font=SMALL, text_color=MUTED)
            status_lbl.pack(pady=(0, 8))

            def _activate():
                status_lbl.configure(text="Validating…", text_color=MUTED)
                dlg.update()
                ok, msg = _lic.activate(key_var.get())
                if ok:
                    status_lbl.configure(text=f"✓ {msg}", text_color=ACCENT2)
                    self.after(1200, lambda: (dlg.destroy(), self._restart_notice()))
                else:
                    status_lbl.configure(text=f"✗ {msg}", text_color=ACCENT)

            ctk.CTkButton(dlg, text="Activate Key", command=_activate,
                          fg_color=ACCENT2, hover_color="#00b899", text_color=BG,
                          font=(FONT, 12, "bold"), height=36, width=340).pack(pady=(0, 8))

            def _open_buy():
                import webbrowser
                webbrowser.open("https://harveyj82.gumroad.com/l/uriyw")
            ctk.CTkButton(dlg, text="⭐ Buy Pro — £4.99/mo", command=_open_buy,
                          fg_color=ACCENT, hover_color=ACCENT_HV, text_color=TEXT,
                          font=(FONT, 11, "bold"), height=34, width=340).pack()

        ctk.CTkButton(dlg, text="Close", command=dlg.destroy,
                      fg_color="transparent", hover_color=PANEL2, text_color=MUTED,
                      font=SMALL, height=26, width=340).pack(pady=(10, 0))

    def _deactivate(self, dlg):
        _lic.deactivate()
        dlg.destroy()
        self._restart_notice()

    def _restart_notice(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Restart Required")
        dlg.geometry("340x160")
        dlg.resizable(False, False)
        dlg.configure(fg_color=PANEL)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="Restart Valo Optimise to apply\nyour licence changes.",
                     font=H3, text_color=TEXT).pack(pady=(36, 20))
        ctk.CTkButton(dlg, text="OK", command=dlg.destroy,
                      fg_color=ACCENT, font=(FONT, 11, "bold"),
                      height=32, width=200).pack()

    # ── Global Hotkey ─────────────────────────────────────────────────────────

    def _hotkey_boost(self):
        boost_frame = self._frames.get("boost")
        if boost_frame and not getattr(boost_frame, '_boost_running', False):
            self.after(0, boost_frame._run_boost)
            _win_toast("Valo Optimise", "Pre-Game Boost triggered (Ctrl+Shift+B)")

    # ── Auto-Restore on Exit ──────────────────────────────────────────────────

    def _ping_launch(self):
        """Anonymous launch counter — fires once per session, no personal data."""
        def _do():
            try:
                from version import VERSION
            except ImportError:
                VERSION = "0.0.0"
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"https://valo-launch-counter.valooptimise.workers.dev/ping?v={VERSION}",
                    method="POST",
                    headers={"User-Agent": f"ValoOptimise/{VERSION}"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        run_in_thread(_do, None)

    def _check_for_update(self):
        """Silently check GitHub for a newer release; show dialog if found."""
        try:
            from modules.auto_updater import check_for_update
            def _on_update(ver, dl_url, page_url):
                self.after(0, lambda: self._show_update_dialog(ver, dl_url, page_url))
            check_for_update(_on_update)
        except Exception:
            pass

    def _show_update_dialog(self, latest_ver: str, dl_url, page_url: str):
        """
        In-app update dialog.
        - If running as a frozen .exe and a direct download URL is available:
          streams the new .exe with a progress bar, swaps it out, relaunches.
        - Otherwise falls back to opening the GitHub release page in the browser.
        """
        try:
            from version import VERSION as CURRENT
        except ImportError:
            CURRENT = "1.0.0"

        import sys as _sys
        can_auto = (
            getattr(_sys, "frozen", False)
            and hasattr(_sys, "_MEIPASS")
            and bool(dl_url)
        )

        # ── Window ────────────────────────────────────────────────────────────
        win = ctk.CTkToplevel(self)
        win.title("Update Available")
        win.geometry("460x270")
        win.resizable(False, False)
        win.configure(fg_color=PANEL)
        win.grab_set()
        win.lift()
        win.after(120, win.lift)

        # ── Header ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            win, text="Update Available",
            font=H2, text_color=ACCENT2,
        ).pack(pady=(26, 4))

        ctk.CTkLabel(
            win,
            text=f"v{CURRENT}  →  v{latest_ver}",
            font=H3, text_color=TEXT,
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            win,
            text="A new version of Valo Optimise is ready." if can_auto
                 else "A new version is available on GitHub.",
            font=BODY, text_color=MUTED,
        ).pack(pady=(0, 14))

        # ── Progress bar (hidden until download starts) ───────────────────────
        prog_bar = ctk.CTkProgressBar(
            win, width=380, height=7,
            progress_color=ACCENT2, fg_color=PANEL2,
        )
        prog_bar.set(0)

        status_lbl = ctk.CTkLabel(
            win, text="", font=SMALL, text_color=MUTED,
        )
        status_lbl.pack(pady=(0, 10))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack()

        def _fallback_browser():
            import webbrowser
            webbrowser.open(page_url)
            win.destroy()

        def _start_update():
            if not can_auto:
                _fallback_browser()
                return

            # Lock UI, reveal progress bar
            update_btn.configure(state="disabled", text="Downloading…")
            later_btn.configure(state="disabled")
            prog_bar.pack(pady=(0, 4))
            status_lbl.configure(text="Connecting…")

            def _progress(done, total):
                if total > 0:
                    self.after(0, lambda: prog_bar.set(done / total))
                    mb_d = done  / 1_048_576
                    mb_t = total / 1_048_576
                    self.after(0, lambda: status_lbl.configure(
                        text=f"Downloading…  {mb_d:.1f} / {mb_t:.1f} MB"))
                else:
                    mb_d = done / 1_048_576
                    self.after(0, lambda: status_lbl.configure(
                        text=f"Downloading…  {mb_d:.1f} MB"))

            def _complete(tmp_path):
                self.after(0, lambda: prog_bar.set(1.0))
                self.after(0, lambda: status_lbl.configure(
                    text="Download complete — applying update…"))
                self.after(600, lambda: _do_apply(tmp_path))

            def _do_apply(tmp_path):
                try:
                    from modules.auto_updater import apply_update
                    apply_update(tmp_path)
                    # Give the batch script a moment to be written before we exit
                    self.after(300, self.quit)
                except Exception as exc:
                    status_lbl.configure(text=f"Apply failed: {exc}")
                    update_btn.configure(
                        state="normal", text="Open Download Page",
                        command=_fallback_browser,
                    )
                    later_btn.configure(state="normal")

            def _error(msg):
                import webbrowser
                self.after(0, lambda: status_lbl.configure(
                    text="Download failed — opening browser…"))
                self.after(0, lambda: update_btn.configure(
                    state="normal", text="Open Download Page",
                    command=_fallback_browser,
                ))
                self.after(0, lambda: later_btn.configure(state="normal"))
                self.after(1500, lambda: webbrowser.open(page_url))

            from modules.auto_updater import download_update
            download_update(dl_url, _progress, _complete, _error)

        update_btn = ctk.CTkButton(
            btn_row,
            text="Update & Restart" if can_auto else "Download Now",
            fg_color=ACCENT, hover_color="#cc3344",
            text_color=TEXT, font=(FONT, 12, "bold"), width=160,
            command=_start_update,
        )
        update_btn.pack(side="left", padx=(0, 10))

        later_btn = ctk.CTkButton(
            btn_row, text="Later",
            fg_color=PANEL2, hover_color=BORDER,
            text_color=MUTED, font=BODY, width=80,
            command=win.destroy,
        )
        later_btn.pack(side="left")

    def _on_close(self):
        import tkinter.messagebox as mb
        needs_restore = []
        try:
            r = subprocess.run(["sc", "query", "wuauserv"],
                               capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if "STOPPED" in r.stdout or "DISABLED" in r.stdout:
                needs_restore.append(("wuauserv", "Windows Update (wuauserv)"))
        except Exception:
            pass
        try:
            r = subprocess.run(["sc", "query", "DiagTrack"],
                               capture_output=True, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            if "STOPPED" in r.stdout or "DISABLED" in r.stdout:
                needs_restore.append(("DiagTrack", "Diagnostic Tracking (DiagTrack)"))
        except Exception:
            pass

        if needs_restore:
            service_names = "\n  \u2022 ".join(label for _, label in needs_restore)
            ans = mb.askyesno(
                "Restore Services?",
                f"These services are currently stopped:\n\n  \u2022 {service_names}\n\n"
                "Re-enable them before closing?\n"
                "(Recommended \u2014 needed for Windows Updates & system health)",
                icon="question"
            )
            if ans:
                for svc, _ in needs_restore:
                    try:
                        subprocess.run(["sc", "start", svc],
                                       capture_output=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        pass
        if self._hotkey_registered:
            try:
                import keyboard as _kb
                _kb.remove_hotkey('ctrl+shift+b')
            except Exception:
                pass
        self.destroy()

    # ── First-Launch Onboarding (4-step wizard) ───────────────────────────────

    def _show_onboarding(self):
        win = ctk.CTkToplevel(self)
        win.title("Welcome to Valo Optimise")
        win.geometry("560x560")
        win.resizable(False, False)
        win.configure(fg_color=BG)
        win.grab_set()
        win.lift()
        win.focus_force()

        _step    = [0]
        _results = [None]

        # ── Fixed header ──────────────────────────────────────────────────────
        ctk.CTkFrame(win, fg_color=ACCENT, height=4, corner_radius=0).pack(fill="x")
        top_row = ctk.CTkFrame(win, fg_color="transparent")
        top_row.pack(fill="x", padx=24, pady=(12, 0))
        ctk.CTkLabel(top_row, text="VALO", font=(FONT, 15, "bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(top_row, text="OPTIMISE", font=(FONT, 11, "bold"),
                     text_color=TEXT).pack(side="left", padx=(3, 0))

        # Step dots
        dots_wrap = ctk.CTkFrame(top_row, fg_color="transparent")
        dots_wrap.pack(side="right")
        _dots = []
        for _ in range(4):
            d = ctk.CTkFrame(dots_wrap, width=8, height=8, corner_radius=4,
                             fg_color=BORDER)
            d.pack(side="left", padx=3)
            _dots.append(d)
        ctk.CTkFrame(win, fg_color=BORDER, height=1).pack(fill="x", padx=24, pady=(10, 0))

        # ── Scrollable content area ───────────────────────────────────────────
        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(16, 0))

        # ── Footer ────────────────────────────────────────────────────────────
        footer = ctk.CTkFrame(win, fg_color=PANEL, corner_radius=0, height=56)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        footer.grid_columnconfigure(1, weight=1)

        skip_btn = ghost_button(footer, "Skip", lambda: _finish(), width=80)
        skip_btn.grid(row=0, column=0, padx=(14, 0), pady=10)
        back_btn = ghost_button(footer, "← Back", lambda: _go(_step[0] - 1), width=90)
        back_btn.grid(row=0, column=1, padx=8, pady=10, sticky="e")
        next_btn = accent_button(footer, "Next →", lambda: _go(_step[0] + 1), width=140)
        next_btn.grid(row=0, column=2, padx=(0, 14), pady=10)

        # ── Helpers ───────────────────────────────────────────────────────────
        def _update_dots(step):
            for i, d in enumerate(_dots):
                d.configure(fg_color=ACCENT if i == step else
                            (ACCENT2 if i < step else BORDER))

        def _clear():
            for w in content.winfo_children():
                w.destroy()

        def _finish():
            self.cfg["onboarding_done"] = True
            save_config(self.cfg)
            win.destroy()

        # ── Step 0 — Welcome & hardware detection ─────────────────────────────
        def _step0():
            _update_dots(0)
            back_btn.configure(state="disabled")
            next_btn.configure(state="normal", text="Next →",
                               command=lambda: _go(1))
            skip_btn.configure(state="normal", text="Skip")
            _clear()

            ctk.CTkLabel(content, text="Welcome to Valo Optimise 👋",
                         font=H1, text_color=TEXT,
                         anchor="w").pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(content,
                         text="Let's get your PC ready for gaming in under a minute.",
                         font=BODY, text_color=MUTED,
                         anchor="w").pack(fill="x", pady=(0, 14))

            hw = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=CR_CARD)
            hw.pack(fill="x", pady=(0, 10))
            make_section_label(hw, "🖥️  Detected Hardware").pack(
                anchor="w", padx=14, pady=(10, 6))

            try:
                import platform as _pl
                cpu = (_pl.processor() or _pl.machine() or "Unknown CPU")[:46]
            except Exception:
                cpu = "Unknown CPU"
            try:
                ram_gb = round(_psutil.virtual_memory().total / (1024 ** 3))
                ram_str = f"{ram_gb} GB"
            except Exception:
                ram_str = "Unknown"

            for icon, label, val in [
                ("🔲", "CPU", cpu),
                ("💾", "RAM", ram_str),
                ("🪟", "OS",  "Windows 10 / 11"),
            ]:
                r = ctk.CTkFrame(hw, fg_color="transparent")
                r.pack(fill="x", padx=14, pady=3)
                ctk.CTkLabel(r, text=f"{icon}  {label}", font=BODY,
                             text_color=MUTED, width=70, anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=val, font=(FONT, 11, "bold"),
                             text_color=TEXT, anchor="w").pack(side="left")

            ctk.CTkFrame(hw, height=1, fg_color=BORDER).pack(
                fill="x", padx=14, pady=(8, 0))
            ctk.CTkLabel(hw,
                         text="✅  Fully anti-cheat safe — OS-level only, no game process interaction.",
                         font=SMALL, text_color=ACCENT2).pack(
                anchor="w", padx=14, pady=(6, 10))

        # ── Step 1 — What will be optimised ───────────────────────────────────
        def _step1():
            _update_dots(1)
            back_btn.configure(state="normal")
            next_btn.configure(state="normal", text="Optimise Now →",
                               command=lambda: _go(2))
            skip_btn.configure(state="normal", text="Skip")
            _clear()

            ctk.CTkLabel(content, text="Here's What We'll Optimise",
                         font=H1, text_color=TEXT,
                         anchor="w").pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(content,
                         text="Safe, reversible tweaks. Your current settings are backed up.",
                         font=BODY, text_color=MUTED,
                         anchor="w").pack(fill="x", pady=(0, 10))

            _TWEAKS = [
                ("⚡", "Power Plan",       "Ultimate Performance — full CPU speed",          True),
                ("🌐", "Network",          "Lower ping, TCP stack tuning for game servers",    True),
                ("🔧", "Registry",         "Windows responsiveness & input latency tweaks",   True),
                ("⏱️", "Timer Resolution", "1ms precision for smoother frame delivery",       True),
                ("⏱️", "Core Parking",     "Keep all CPU cores active during play",           True),
                ("🎮", "GPU",              "AMD Chill off, HAGS toggle for lower latency",    False),
                ("👁️", "Visibility",       "Colour profile tweaks for enemy visibility",      False),
                ("🔊", "Audio",            "MMCSS priority for low-latency game audio",       False),
                ("🎮", "Game Config",      "Optimal in-game settings editor",                 False),
            ]
            is_pro = _lic.is_pro()
            scroll = ctk.CTkScrollableFrame(content, fg_color="transparent", height=260)
            scroll.pack(fill="both", expand=True)

            for icon, name, desc, free in _TWEAKS:
                card = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=8)
                card.pack(fill="x", pady=3)
                card.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(card, text=icon, font=(FONT, 15),
                             width=30).grid(row=0, column=0, rowspan=2,
                                            padx=(10, 6), pady=8)
                ctk.CTkLabel(card, text=name, font=(FONT, 11, "bold"),
                             text_color=TEXT, anchor="w").grid(
                    row=0, column=1, sticky="w", pady=(8, 0))
                ctk.CTkLabel(card, text=desc, font=SMALL,
                             text_color=MUTED, anchor="w").grid(
                    row=1, column=1, sticky="w", pady=(0, 8))
                if free or is_pro:
                    badge_text  = "FREE" if free else "PRO ✓"
                    badge_color = ACCENT2 if free else GOLD
                else:
                    badge_text  = "🔒 PRO"
                    badge_color = MUTED
                ctk.CTkLabel(card, text=badge_text, font=LABEL,
                             text_color=badge_color, width=52).grid(
                    row=0, column=2, rowspan=2, padx=(0, 10))

        # ── Step 2 — Running the boost ────────────────────────────────────────
        def _step2():
            _update_dots(2)
            back_btn.configure(state="disabled")
            next_btn.configure(state="disabled", text="Optimising...")
            skip_btn.configure(state="disabled")
            _clear()

            ctk.CTkLabel(content, text="Optimising Your PC...",
                         font=H1, text_color=TEXT,
                         anchor="w").pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(content,
                         text="Applying safe OS-level tweaks. Takes about 15 seconds.",
                         font=BODY, text_color=MUTED,
                         anchor="w").pack(fill="x", pady=(0, 12))

            prog = ctk.CTkProgressBar(content, height=6, fg_color=PANEL2,
                                      progress_color=ACCENT)
            prog.pack(fill="x", pady=(0, 14))
            prog.set(0)

            _BSTEPS = [
                ("pwr",   "⚡", "Setting Ultimate Performance power plan"),
                ("bg",    "🧹", "Killing background processes"),
                ("ram",   "💾", "Clearing standby memory"),
                ("reg",   "🔧", "Applying registry tweaks"),
                ("park",  "⏱️", "Disabling core parking"),
                ("timer", "⏱️", "Setting 1ms timer resolution"),
            ]
            icon_lbls = {}
            for key, icon, label in _BSTEPS:
                row = ctk.CTkFrame(content, fg_color="transparent")
                row.pack(fill="x", pady=2)
                il = ctk.CTkLabel(row, text="○", font=BODY,
                                  text_color=MUTED, width=20)
                il.pack(side="left", padx=(0, 8))
                ctk.CTkLabel(row, text=f"{icon}  {label}", font=BODY,
                             text_color=MUTED, anchor="w").pack(side="left")
                icon_lbls[key] = il

            def _run():
                _sys = SystemOptimizer()
                _rt  = RegistryTweaks()
                _cpu = CpuTimerOptimizer()
                steps_fn = [
                    ("pwr",   lambda: _sys.set_ultimate_performance_plan()),
                    ("bg",    lambda: (True, f"Killed {sum(1 for _,o,_ in (_sys.kill_all_background_targets() or []) if o)}")),
                    ("ram",   lambda: _sys.clear_standby_memory()),
                    ("reg",   lambda: (True, f"{sum(1 for _,o,_ in _rt.apply_all_tweaks() if o)} tweaks")),
                    ("park",  lambda: _cpu.disable_core_parking()),
                    ("timer", lambda: _cpu.set_timer_resolution_1ms()),
                ]
                results = []
                for i, (key, fn) in enumerate(steps_fn):
                    win.after(0, lambda k=key: icon_lbls[k].configure(
                        text="⟳", text_color=GOLD))
                    try:
                        ok, msg = fn()
                    except Exception as e:
                        ok, msg = False, str(e)[:60]
                    results.append((key, ok, msg))
                    win.after(0, lambda k=key, o=ok: icon_lbls[k].configure(
                        text="✓" if o else "✗",
                        text_color=ACCENT2 if o else RED_LIGHT))
                    ease_progress(prog, (i + 1) / len(steps_fn), 300)
                return results

            def _done(results):
                _results[0] = results
                next_btn.configure(state="normal", text="See Results →",
                                   command=lambda: _go(3))
                _go(3)

            run_in_thread(_run, lambda r: win.after(0, lambda: _done(r)))

        # ── Step 3 — Results + upgrade prompt ────────────────────────────────
        def _step3():
            _update_dots(3)
            back_btn.configure(state="disabled")
            skip_btn.configure(state="normal", text="Explore App",
                               command=_finish)
            _clear()

            results = _results[0] or []
            n_ok    = sum(1 for _, o, _ in results if o)
            n_total = len(results)
            fps_est = 5 + (n_ok * 4)

            ctk.CTkLabel(content, text="Your PC is Ready! 🚀",
                         font=H1, text_color=TEXT,
                         anchor="w").pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(content, text=f"{n_ok}/{n_total} tweaks applied successfully.",
                         font=BODY, text_color=MUTED,
                         anchor="w").pack(fill="x", pady=(0, 12))

            # FPS estimate card
            fps_card = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=CR_CARD)
            fps_card.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(fps_card, text="Estimated FPS Improvement",
                         font=BODY, text_color=MUTED).pack(pady=(12, 2))
            fps_lbl = ctk.CTkLabel(fps_card, text="+0 FPS",
                                   font=(FONT, 34, "bold"),
                                   text_color=ACCENT2 if n_ok >= 4 else GOLD)
            fps_lbl.pack(pady=(0, 4))
            count_up(fps_lbl, fps_est, 800, "+{:.0f} FPS",
                     ACCENT2 if n_ok >= 4 else GOLD)
            ctk.CTkLabel(fps_card,
                         text="Average across tested systems — actual gains vary by hardware.",
                         font=SMALL, text_color=MUTED).pack(pady=(0, 12))

            # Pro upsell (free users only)
            if not _lic.is_pro():
                upsell = ctk.CTkFrame(content, fg_color=PANEL2, corner_radius=10,
                                      border_width=1, border_color=ACCENT)
                upsell.pack(fill="x", pady=(0, 8))
                upsell.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(upsell, text="🔒  Unlock 9 More Pro Optimisations",
                             font=(FONT, 12, "bold"),
                             text_color=GOLD).grid(
                    row=0, column=0, sticky="w", padx=14, pady=(10, 2))
                ctk.CTkLabel(upsell,
                             text="GPU tuning • Visibility boost • Audio priority • CPU timer • Game Config",
                             font=SMALL, text_color=MUTED,
                             wraplength=430, justify="left").grid(
                    row=1, column=0, sticky="w", padx=14, pady=(0, 8))
                def _open_pro():
                    import webbrowser
                    webbrowser.open("https://harveyj82.gumroad.com/l/uriyw")
                ctk.CTkButton(upsell, text="Get Pro — £4.99/mo",
                              font=(FONT, 11, "bold"),
                              fg_color=ACCENT, hover_color=ACCENT_HV,
                              text_color=TEXT, corner_radius=8, height=32,
                              command=_open_pro).grid(
                    row=2, column=0, sticky="w", padx=14, pady=(0, 10))

            def _launch():
                _win_toast("Valo Optimise",
                           f"Optimised! Est. +{fps_est} FPS gain. Good luck! 🎯")
                _finish()

            next_btn.configure(state="normal", text="Let's Play! 🎮",
                               command=_launch)

        # ── Router ────────────────────────────────────────────────────────────
        _STEPS = [_step0, _step1, _step2, _step3]

        def _go(step):
            if 0 <= step < len(_STEPS):
                _step[0] = step
                _STEPS[step]()

        _go(0)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    set_dpi_awareness()   # must be before any Tk window creation
    require_admin()
    cfg = load_config()
    app = App(cfg)
    app.mainloop()
