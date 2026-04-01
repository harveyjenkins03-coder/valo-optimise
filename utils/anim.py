# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
utils/anim.py — Lightweight after()-based UI animations for CustomTkinter.
No external dependencies; uses only the Tk event loop.
"""


def _safe_set(widget, attr, value):
    try:
        widget.configure(**{attr: value})
    except Exception:
        pass


def count_up(widget, end: float, duration_ms: int = 700,
             fmt: str = "{:.0f}", color: str = None):
    """
    Animate a CTkLabel's text from 0 → end with ease-out cubic.
    Optionally set text_color=color simultaneously.
    """
    steps    = max(16, duration_ms // 16)
    interval = max(1,  duration_ms // steps)

    def _step(i):
        t     = i / steps
        eased = 1 - (1 - t) ** 3        # ease-out cubic
        val   = end * eased
        try:
            kw = {"text": fmt.format(val)}
            if color:
                kw["text_color"] = color
            widget.configure(**kw)
        except Exception:
            return
        if i < steps:
            widget.after(interval, lambda: _step(i + 1))

    _step(0)


def ease_progress(bar, target: float, duration_ms: int = 420):
    """
    Animate a CTkProgressBar from its current value → target.
    Uses ease-out cubic for a smooth, confident feel.
    """
    try:
        current = bar.get()
    except Exception:
        current = 0.0

    steps    = max(16, duration_ms // 16)
    interval = max(1,  duration_ms // steps)
    delta    = target - current

    def _step(i):
        t     = i / steps
        eased = 1 - (1 - t) ** 3
        try:
            bar.set(current + delta * eased)
        except Exception:
            return
        if i < steps:
            bar.after(interval, lambda: _step(i + 1))

    _step(0)


class Pulse:
    """
    Continuously pulses a widget attribute between two color values via after().

    Usage:
        p = Pulse(btn, "#ff4655", "#e63946", half_period_ms=1600)
        # later:
        p.stop(restore_color="#ff4655")
    """

    def __init__(self, widget, color_a: str, color_b: str,
                 half_period_ms: int = 1600, attr: str = "fg_color"):
        self._w       = widget
        self._ca      = color_a
        self._cb      = color_b
        self._hp      = half_period_ms
        self._attr    = attr
        self._running = True
        self._phase   = 0
        self._tick()

    def _tick(self):
        if not self._running:
            return
        color = self._ca if self._phase % 2 == 0 else self._cb
        _safe_set(self._w, self._attr, color)
        self._phase += 1
        try:
            self._w.after(self._hp, self._tick)
        except Exception:
            self._running = False

    def stop(self, restore_color: str = None):
        self._running = False
        if restore_color is not None:
            _safe_set(self._w, self._attr, restore_color)


def flash_bg(widget, flash_color: str, original_color: str,
             duration_ms: int = 550):
    """
    Briefly flash a widget's fg_color to flash_color, then restore original_color.
    Used for step-completion row highlights.
    """
    _safe_set(widget, "fg_color", flash_color)
    try:
        widget.after(duration_ms,
                     lambda: _safe_set(widget, "fg_color", original_color))
    except Exception:
        pass


def slide_in(widget, parent, duration_ms: int = 160):
    """Slide a frame in from the right edge, then switch to pack layout."""
    try:
        parent.update_idletasks()
        width = parent.winfo_width()
    except Exception:
        widget.pack(fill="both", expand=True)
        return

    steps = max(8, duration_ms // 16)
    interval = max(1, duration_ms // steps)

    widget.place(x=width, y=0, relwidth=1, relheight=1)

    def _step(i):
        t = i / steps
        eased = 1 - (1 - t) ** 3
        x = int(width * (1 - eased))
        try:
            widget.place_configure(x=x)
        except Exception:
            return
        if i < steps:
            widget.after(interval, lambda: _step(i + 1))
        else:
            try:
                widget.place_forget()
                widget.pack(fill="both", expand=True)
            except Exception:
                pass

    _step(0)


def show_toast(parent, message, toast_type="success", duration_ms=3000):
    """In-app toast notification that appears in the top-right corner."""
    colors = {"success": "#3DDC84", "error": "#FF5A6A", "info": "#FFCC44"}
    border_color = colors.get(toast_type, colors["info"])
    toast = None
    try:
        import customtkinter as ctk
        toast = ctk.CTkFrame(parent, fg_color="#162A40", corner_radius=6,
                             border_width=1, border_color=border_color)
        toast.place(relx=1.0, y=10, anchor="ne", x=-20)
        ctk.CTkLabel(toast, text=message, font=("Sora", 12),
                     text_color=border_color).pack(padx=16, pady=8)
        parent.after(duration_ms, lambda: _safe_destroy(toast))
    except Exception:
        pass

def _safe_destroy(widget):
    try:
        widget.destroy()
    except Exception:
        pass


def fade_in_window(window, duration_ms: int = 260, steps: int = 16):
    """
    Fade a CTk/Tk top-level window from alpha=0 to alpha=1.
    Call after the window is shown.
    """
    interval = max(1, duration_ms // steps)

    def _step(i):
        try:
            window.attributes("-alpha", i / steps)
            if i < steps:
                window.after(interval, lambda: _step(i + 1))
        except Exception:
            pass

    try:
        window.attributes("-alpha", 0)
        window.after(20, lambda: _step(1))
    except Exception:
        pass
