# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.

"""
fps_card.py — Shareable before/after performance card generator
===============================================================
Generates a 1200x675 PNG card showing before/after benchmark scores
and metric improvements. Ready to share on Reddit, Discord, Twitter.
"""

import os
import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Colours ──────────────────────────────────────────────────────────────────
C_BG     = (10,  14,  26)
C_CARD   = (20,  24,  36)
C_CARD2  = (14,  18,  28)
C_RED    = (255, 70,  85)
C_TEAL   = (0,   212, 170)
C_GOLD   = (255, 215, 0)
C_WHITE  = (255, 255, 255)
C_TEXT   = (240, 244, 255)
C_MUTED  = (100, 112, 130)
C_BORDER = (30,  36,  53)
C_FIXED  = (0,   45,  38)     # dark teal pill fill
C_REMAIN = (18,  22,  32)     # dark pill fill

W, H = 1200, 675

# ── Font helpers ──────────────────────────────────────────────────────────────
_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
]
_REG_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]

def _find_font(candidates):
    return next((f for f in candidates if os.path.exists(f)), None)

def _load(path, size):
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


def _grade(score: int):
    if score >= 90: return "ELITE",        C_TEAL
    if score >= 75: return "COMPETITIVE",  C_TEAL
    if score >= 55: return "AVERAGE",      C_GOLD
    if score >= 35: return "NEEDS WORK",   (255, 153, 0)
    return               "UNOPTIMISED",    C_RED


def generate_card(
    before_score: int,
    after_score: int,
    before_metrics: dict,
    after_metrics: dict,
    out_path: str | None = None,
) -> str:
    """
    Generate a shareable results card PNG and return its file path.

    before_metrics / after_metrics: {key: {"value": str, "passed": bool}}
    """
    if out_path is None:
        desktop = Path.home() / "Desktop"
        stamp   = datetime.date.today().strftime("%Y-%m-%d")
        out_path = str(desktop / f"ValoOptimise_Results_{stamp}.png")

    bold_path = _find_font(_BOLD_CANDIDATES)
    reg_path  = _find_font(_REG_CANDIDATES)

    def fb(sz): return _load(bold_path or reg_path, sz)
    def fr(sz): return _load(reg_path  or bold_path, sz)

    img  = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    # ── Subtle grid ───────────────────────────────────────────────────────────
    grid_col = (16, 20, 32)
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=grid_col, width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=grid_col, width=1)

    # ── Top accent bar ────────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (W, 5)], fill=C_RED)

    # ── Header row ───────────────────────────────────────────────────────────
    # Logo
    valo_w = int(draw.textlength("VALO", font=fb(30)))
    draw.text((44, 20), "VALO",     font=fb(30), fill=C_WHITE)
    draw.text((44 + valo_w, 20), "OPTIMISE", font=fb(30), fill=C_RED)
    draw.text((44, 58), "PERFORMANCE REPORT", font=fr(12), fill=C_MUTED)

    # Beta pill (top right)
    beta_f   = fb(11)
    beta_txt = "PUBLIC BETA"
    beta_w   = int(draw.textlength(beta_txt, font=beta_f)) + 28
    bx1, by1, bx2, by2 = W - 44 - beta_w, 22, W - 44, 46
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=11, fill=(40, 10, 14))
    draw.rounded_rectangle([(bx1, by1), (bx2, by2)], radius=11, outline=C_RED, width=1)
    draw.text(((bx1+bx2)//2, (by1+by2)//2), beta_txt, font=beta_f, fill=C_RED, anchor="mm")

    # Date
    date_str = datetime.date.today().strftime("%d %b %Y")
    draw.text((W - 44, 56), date_str, font=fr(11), fill=C_MUTED, anchor="ra")

    # Header divider
    draw.rectangle([(44, 86), (W - 44, 87)], fill=C_BORDER)

    # ── Score panels ─────────────────────────────────────────────────────────
    PAD, PY1, PY2 = 44, 104, 320
    MID = W // 2

    # Before panel
    draw.rounded_rectangle([(PAD, PY1), (MID - 20, PY2)], radius=14, fill=C_CARD)
    b_grade, b_col = _grade(before_score)
    draw.text((PAD + (MID - 20 - PAD)//2, PY1 + 22), "BEFORE",
              font=fr(12), fill=C_MUTED, anchor="mm")
    draw.text((PAD + (MID - 20 - PAD)//2, PY1 + 118), str(before_score),
              font=fb(96), fill=b_col, anchor="mm")
    draw.text((PAD + (MID - 20 - PAD)//2, PY1 + 178), "/ 100",
              font=fr(13), fill=C_MUTED, anchor="mm")
    draw.text((PAD + (MID - 20 - PAD)//2, PY2 - 24), b_grade,
              font=fb(14), fill=b_col, anchor="mm")

    # After panel
    draw.rounded_rectangle([(MID + 20, PY1), (W - PAD, PY2)], radius=14, fill=C_CARD)
    a_grade, a_col = _grade(after_score)
    draw.text((MID + 20 + (W - PAD - MID - 20)//2, PY1 + 22), "AFTER",
              font=fr(12), fill=C_MUTED, anchor="mm")
    draw.text((MID + 20 + (W - PAD - MID - 20)//2, PY1 + 118), str(after_score),
              font=fb(96), fill=a_col, anchor="mm")
    draw.text((MID + 20 + (W - PAD - MID - 20)//2, PY1 + 178), "/ 100",
              font=fr(13), fill=C_MUTED, anchor="mm")
    draw.text((MID + 20 + (W - PAD - MID - 20)//2, PY2 - 24), a_grade,
              font=fb(14), fill=a_col, anchor="mm")

    # Delta badge (centred between panels)
    delta      = after_score - before_score
    delta_str  = f"+{delta}" if delta >= 0 else str(delta)
    delta_col  = C_TEAL if delta > 0 else (C_RED if delta < 0 else C_MUTED)
    arrow      = "↑" if delta > 0 else ("↓" if delta < 0 else "—")
    dx1, dx2   = MID - 56, MID + 56
    dy1, dy2   = PY1 + 58, PY2 - 58
    draw.rounded_rectangle([(dx1, dy1), (dx2, dy2)], radius=14, fill=C_CARD2)
    draw.rounded_rectangle([(dx1, dy1), (dx2, dy2)], radius=14, outline=delta_col, width=2)
    mid_y = (dy1 + dy2) // 2
    draw.text((MID, mid_y - 26), delta_str, font=fb(40), fill=delta_col, anchor="mm")
    draw.text((MID, mid_y + 14), "PTS",     font=fb(11), fill=C_MUTED,   anchor="mm")
    draw.text((MID, mid_y + 34), arrow,     font=fb(18), fill=delta_col, anchor="mm")

    # ── Metrics section ───────────────────────────────────────────────────────
    draw.rectangle([(PAD, PY2 + 12), (W - PAD, PY2 + 13)], fill=C_BORDER)

    # Classify metrics
    try:
        from modules.benchmark import METRIC_ORDER, _LABELS
        order  = METRIC_ORDER
        labels = _LABELS
    except Exception:
        order  = list(after_metrics.keys())
        labels = {k: k for k in order}

    fixed     = []   # was failing → now passing
    still_bad = []   # still failing

    for key in order:
        bm     = before_metrics.get(key, {})
        am     = after_metrics.get(key, {})
        b_pass = bm.get("passed", False)
        a_pass = am.get("passed", False)
        lbl    = labels.get(key, key)
        if not b_pass and a_pass:
            fixed.append(lbl)
        elif not a_pass:
            still_bad.append(lbl)

    # Section label
    section_y = PY2 + 22
    n_fixed = len(fixed)
    n_total = len(order)
    draw.text((PAD, section_y + 8), "IMPROVEMENTS",
              font=fb(11), fill=C_MUTED)
    summary = f"{n_fixed} metrics fixed  ·  {n_total - n_fixed - (n_total - n_fixed - len(still_bad))} already optimal"
    draw.text((W - PAD, section_y + 8), summary, font=fr(10), fill=C_MUTED, anchor="ra")

    # Render pills
    pill_f  = fb(11)
    pill_fr = fr(11)
    pill_h  = 30
    px, py  = PAD, section_y + 32
    MAX_Y   = H - 78

    for lbl in fixed:
        txt = f"\u2713  {lbl}"
        tw  = int(draw.textlength(txt, font=pill_f)) + 24
        if px + tw > W - PAD:
            px  = PAD
            py += pill_h + 8
        if py + pill_h > MAX_Y:
            break
        draw.rounded_rectangle([(px, py), (px + tw, py + pill_h)], radius=8, fill=C_FIXED)
        draw.rounded_rectangle([(px, py), (px + tw, py + pill_h)], radius=8,
                                outline=C_TEAL, width=1)
        draw.text((px + 12, py + pill_h // 2), txt, font=pill_f, fill=C_TEAL, anchor="lm")
        px += tw + 8

    # New row for remaining
    px  = PAD
    py += pill_h + 10

    for lbl in still_bad:
        txt = f"\u2717  {lbl}"
        tw  = int(draw.textlength(txt, font=pill_fr)) + 24
        if px + tw > W - PAD:
            px  = PAD
            py += pill_h + 8
        if py + pill_h > MAX_Y:
            break
        draw.rounded_rectangle([(px, py), (px + tw, py + pill_h)], radius=8, fill=C_REMAIN)
        draw.text((px + 12, py + pill_h // 2), txt, font=pill_fr, fill=C_MUTED, anchor="lm")
        px += tw + 8

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.rectangle([(0, H - 66), (W, H)],       fill=C_CARD)
    draw.rectangle([(0, H - 67), (W, H - 66)],  fill=C_BORDER)

    draw.text((PAD, H - 33), "valooptimise.com",
              font=fb(13), fill=C_WHITE, anchor="lm")
    draw.text((PAD + int(draw.textlength("valooptimise.com", font=fb(13))) + 18, H - 33),
              "Free PC optimiser for Valorant — Public Beta",
              font=fr(11), fill=C_MUTED, anchor="lm")

    # Ko-fi (right)
    draw.text((W - PAD, H - 40), "\u2615  ko-fi.com/valooptimise",
              font=fb(12), fill=C_GOLD, anchor="rm")
    draw.text((W - PAD, H - 22), "Support the beta",
              font=fr(10), fill=C_MUTED, anchor="rm")

    # Bottom red bar
    draw.rectangle([(0, H - 3), (W, H)], fill=C_RED)

    img.save(out_path, "PNG", optimize=True)
    return out_path
