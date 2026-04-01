#!/usr/bin/env python3
# Copyright (c) 2026 Valo Optimise Ltd. All rights reserved.
# Proprietary and confidential. See LICENSE for terms.
"""
create_icon.py — Generate assets/icon.ico for Valo Optimise
Run:  python create_icon.py
Deps: Pillow  (already in requirements.txt)
"""

from PIL import Image, ImageDraw
import os

# ── Brand colours ──────────────────────────────────────────────────────────────
_TOP  = (255,  70,  85, 255)   # #ff4655  Valo red (top of gradient)
_BOT  = (168,  22,  38, 255)   # #a81626  deep red (bottom of gradient)
_WHITE = (255, 255, 255, 255)
_NONE  = (0,   0,   0,   0)

# Lightning bolt — 6-point polygon (normalised 0-100 grid, verified non-intersecting)
#   1→2  (62,4)→(26,52)   right edge of upper bolt  (↙ diagonal)
#   2→3  (26,52)→(46,52)  inner notch                (→ step)
#   3→4  (46,52)→(14,96)  right edge of lower bolt   (↙ diagonal)
#   4→5  (14,96)→(54,46)  left edge of lower bolt    (↗ diagonal)
#   5→6  (54,46)→(76,46)  outer waist step            (→ step)
#   6→1  (76,46)→(62, 4)  left edge of upper bolt    (↖ diagonal)
_BOLT_100 = [(62, 4), (26, 52), (46, 52), (14, 96), (54, 46), (76, 46)]

# Slightly thicker bolt for very small sizes (≤32 px)
_BOLT_100_SM = [(58, 3), (18, 54), (42, 54), (10, 97), (56, 45), (82, 45)]


def _make_frame(size: int) -> Image.Image:
    img   = Image.new('RGBA', (size, size), _NONE)
    draw  = ImageDraw.Draw(img)
    r_max = max(2, size // 6)          # corner radius — tighter for small sizes

    # ── Gradient fill (row by row) ──────────────────────────────────────────
    for y in range(size):
        t = y / max(size - 1, 1)
        row_colour = (
            round(_TOP[0] + (_BOT[0] - _TOP[0]) * t),
            round(_TOP[1] + (_BOT[1] - _TOP[1]) * t),
            round(_TOP[2] + (_BOT[2] - _TOP[2]) * t),
            255,
        )
        draw.line([(0, y), (size - 1, y)], fill=row_colour)

    # ── Rounded-rectangle mask (clip gradient to rounded square) ───────────
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=r_max, fill=255
    )
    clipped = Image.new('RGBA', (size, size), _NONE)
    clipped.paste(img, mask=mask)

    # ── Lightning bolt ──────────────────────────────────────────────────────
    draw2  = ImageDraw.Draw(clipped)
    raw    = _BOLT_100_SM if size <= 32 else _BOLT_100
    scale  = size / 100.0
    bolt   = [(x * scale, y * scale) for x, y in raw]
    draw2.polygon(bolt, fill=_WHITE)

    # ── Subtle highlight on bolt for larger sizes (semi-transparent overlay) ─
    if size >= 48:
        # Thin bright strip along top-left edge of bolt for a "shine"
        shrink = 0.96
        cx     = size * 0.47          # approximate bolt centroid x
        cy     = size * 0.50          # approximate bolt centroid y
        hi_bolt = [
            ((x - cx) * shrink + cx, (y - cy) * shrink + cy)
            for x, y in bolt
        ]
        draw2.polygon(hi_bolt, fill=(255, 255, 255, 80))

    return clipped


def _build_ico(frames: list) -> bytes:
    """
    Manually assemble a multi-size ICO file (PNG-inside-ICO, 32-bit RGBA).
    Windows Explorer, PyInstaller and Tkinter all support this modern format.
    """
    import struct, io

    # Encode each frame as PNG bytes
    png_chunks = []
    for frame in frames:
        buf = io.BytesIO()
        frame.convert('RGBA').save(buf, format='PNG')
        png_chunks.append(buf.getvalue())

    n = len(frames)
    header     = struct.pack('<HHH', 0, 1, n)   # reserved=0, type=1, count=n
    dir_size   = n * 16
    data_start = 6 + dir_size                    # offset of first image data

    directory  = b''
    offset     = data_start
    for frame, png in zip(frames, png_chunks):
        w, h = frame.size
        directory += struct.pack(
            '<BBBBHHII',
            0 if w >= 256 else w,   # width  (0 encodes 256)
            0 if h >= 256 else h,   # height (0 encodes 256)
            0,                      # colour count
            0,                      # reserved
            1,                      # planes
            32,                     # bits-per-pixel
            len(png),               # byte size of image data
            offset,                 # byte offset of image data
        )
        offset += len(png)

    return header + directory + b''.join(png_chunks)


def main():
    os.makedirs('assets', exist_ok=True)
    sizes  = [16, 24, 32, 48, 64, 128, 256]
    frames = [_make_frame(s) for s in sizes]

    ico_path = os.path.join('assets', 'icon.ico')
    ico_data = _build_ico(frames)
    with open(ico_path, 'wb') as f:
        f.write(ico_data)

    # Verify
    import struct
    n_images = struct.unpack_from('<H', ico_data, 4)[0]
    print(f'OK  {ico_path}  — {len(ico_data):,} bytes  ({n_images} sizes: {sizes})')

    # 256 px PNG for reference / taskbar use
    png_path = os.path.join('assets', 'icon_256.png')
    frames[-1].save(png_path, format='PNG')
    print(f'OK  {png_path}')


if __name__ == '__main__':
    main()
