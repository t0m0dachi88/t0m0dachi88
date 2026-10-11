"""
Photo -> animated ASCII portrait SVG for a GitHub profile README.

  python scripts/make_ascii_portrait.py photo.jpg assets/ascii-portrait.svg
  env: CROP="x0,y0,x1,y1" (source px, crop tight to the face first)
       COLS=110  EDGE=0.5  STATIC=1 (final frame only, for previews)

Pipeline: crop -> remove background (rembg) -> CLAHE local contrast ->
edge emphasis (glasses, beard line, smile) -> subject on white ->
dark pixels become dense glyphs, skin/highlights stay open (reads like ink).
SVG: terminal window; every row wipes in left-to-right with a block cursor
riding the edge, rows staggered top to bottom; ends on a typed prompt line.
"""
import os
import sys
from xml.sax.saxutils import escape

import cv2
import numpy as np
from PIL import Image

COLS = int(os.environ.get("COLS", "150"))
EDGE = float(os.environ.get("EDGE", "0.75"))
DETAIL = float(os.environ.get("DETAIL", "1.4"))  # unsharp-mask strength for small features
GAMMA = float(os.environ.get("GAMMA", "1.3"))
FLOOR = float(os.environ.get("FLOOR", "0.1"))   # minimum density inside the person, so light skin still shows its shape   # >1 keeps skin and mid-tones open, darks stay dense
STATIC = os.environ.get("STATIC") == "1"
RAMP = " .'`:-~=+*cs%#@"          # open -> dense ; dark pixels get dense glyphs
INK = "#d0d7de"                    # one soft monochrome ink (colour per glyph looks like static)

W = 370
PAD_X, TOP, BOTTOM = 16, 46, 46
CHAR_W = (W - 2 * PAD_X) / COLS
LINE_H = CHAR_W * 1.85
FONT = CHAR_W * 1.66
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def _cfg():
    sys.path.insert(0, os.path.dirname(__file__))
    from config import load
    return load()


def prep(path):
    img = Image.open(path).convert("RGB")
    crop = os.environ.get("CROP") or _cfg()["portrait"].get("crop", "")
    if crop:
        img = img.crop(tuple(int(v) for v in crop.split(",")))
    try:
        from rembg import new_session, remove
        rgba = np.array(remove(img, session=new_session("u2net_human_seg")))
    except Exception as e:
        print("rembg unavailable, keeping background:", e)
        rgba = np.array(img.convert("RGBA"))
    # trim only empty background around the person (the person is never cut)
    ys, xs = np.where(rgba[:, :, 3] > 20)
    if len(xs):
        m = int(0.02 * max(rgba.shape[:2]))
        rgba = rgba[max(0, ys.min() - m):ys.max() + m + 1, max(0, xs.min() - m):xs.max() + m + 1]
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)

    inside = alpha > 0.5
    lo, hi = np.percentile(gray[inside], [1, 99]) if inside.any() else (0, 255)
    gray = np.clip((gray.astype(np.float32) - lo) / max(1, hi - lo) * 255, 0, 255).astype(np.uint8)
    gray = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray).astype(np.float32)

    # local detail boost (unsharp mask): pulls out eyes, frames, teeth that sit in mid-tones
    if DETAIL:
        base = cv2.GaussianBlur(gray, (0, 0), gray.shape[1] / 45)
        gray = np.clip(gray + DETAIL * (gray - base), 0, 255)

    # darken along edges so outlines (frames, jaw, smile) print as strokes
    blur = cv2.GaussianBlur(gray, (0, 0), max(1.0, gray.shape[1] / 260))
    mag = cv2.magnitude(cv2.Sobel(blur, cv2.CV_32F, 1, 0), cv2.Sobel(blur, cv2.CV_32F, 0, 1))
    mag = np.clip(mag / (np.percentile(mag[inside], 96) + 1e-6), 0, 1) if inside.any() else mag * 0
    gray = gray * (1 - EDGE * mag)

    gray = gray * alpha + 255 * (1 - alpha)          # subject on white -> background is blank
    return gray.astype(np.uint8), alpha


def to_ascii(gray, alpha):
    h, w = gray.shape
    rows = max(1, round(COLS * (h / w) * (CHAR_W / LINE_H)))
    small = cv2.resize(gray, (COLS, rows), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    a = cv2.resize(alpha, (COLS, rows), interpolation=cv2.INTER_AREA)
    lines = []
    for r in range(rows):
        row = ""
        for c in range(COLS):
            d = max(FLOOR, (1 - small[r, c]) ** GAMMA) if a[r, c] > 0.35 else 0   # darkness -> density; skin keeps a faint texture
            row += RAMP[min(len(RAMP) - 1, int(d * len(RAMP)))]
        lines.append(row.rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def svg(lines, name=None, user=None):
    if name is None or user is None:
        cfg = _cfg()
        name, user = name or cfg["name"], user or cfg["handle"]
    global TOP
    H = round(TOP + len(lines) * LINE_H + BOTTOM)
    min_h = int(os.environ.get("MIN_H", "0"))       # match the info card: centre the art vertically
    if H < min_h:
        TOP += (min_h - H) / 2
        H = min_h
    step, dur, start = 0.045, 0.5, 0.35
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">', '<defs>']
    for i in range(len(lines)):
        y = TOP + i * LINE_H
        anim = "" if STATIC else (f'<animate attributeName="width" from="0" to="{W}" begin="{start + i * step:.3f}s" '
                                  f'dur="{dur}s" fill="freeze"/>')
        o.append(f'<clipPath id="r{i}"><rect x="0" y="{y - LINE_H:.2f}" width="{W if STATIC else 0}" '
                 f'height="{LINE_H + 1:.2f}">{anim}</rect></clipPath>')
    o.append('</defs>')

    o.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>')
    o.append(f'<path d="M12 .5h{W - 24}a11.5 11.5 0 0 1 11.5 11.5v16H.5V12A11.5 11.5 0 0 1 12 .5z" fill="#161b22"/>')
    o.append(f'<line x1="1" y1="28.5" x2="{W - 1}" y2="28.5" stroke="#30363d"/>')
    for k, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        o.append(f'<circle cx="{18 + k * 16}" cy="14.5" r="5" fill="{col}"/>')
    o.append(f'<text x="{W / 2}" y="18.5" text-anchor="middle" font-family="{MONO}" font-size="11" '
             f'fill="#7d8590">{escape(user)}@github: ~$ ./portrait.sh</text>')

    o.append(f'<g font-family="{MONO}" font-size="{FONT:.2f}" fill="{INK}">')
    for i, line in enumerate(lines):
        if not line:
            continue
        lead = len(line) - len(line.lstrip(" "))
        body = line.lstrip(" ")
        x0 = PAD_X + lead * CHAR_W
        # browsers collapse SVG whitespace: anchor each row at its first glyph, nbsp inside,
        # textLength pins the row to the grid in whatever monospace font the viewer has
        o.append(f'<text x="{x0:.2f}" y="{TOP + i * LINE_H:.2f}" textLength="{len(body) * CHAR_W:.2f}" '
                 f'lengthAdjust="spacingAndGlyphs" clip-path="url(#r{i})">{escape(body).replace(" ", "&#160;")}</text>')
    o.append('</g>')

    if not STATIC:
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            y, b = TOP + i * LINE_H, start + i * step
            o.append(f'<rect x="{PAD_X}" y="{y - LINE_H * 0.8:.2f}" width="{CHAR_W * 1.4:.2f}" height="{LINE_H * 0.9:.2f}" '
                     f'fill="{INK}" opacity="0"><set attributeName="opacity" to=".85" begin="{b:.3f}s"/>'
                     f'<animate attributeName="x" from="{PAD_X}" to="{W}" begin="{b:.3f}s" dur="{dur}s" fill="freeze"/>'
                     f'<set attributeName="opacity" to="0" begin="{b + dur:.3f}s"/></rect>')

    # footer: separator + prompt that types the name, then a blinking cursor
    fy = H - 17
    end = 0 if STATIC else start + len(lines) * step + dur
    o.append(f'<line x1="1" y1="{H - 34.5}" x2="{W - 1}" y2="{H - 34.5}" stroke="#30363d"/>')
    fs, cw = 12, 12 * 0.602
    prompt = f"{user}@github:~$ whoami "
    o.append(f'<text x="{PAD_X}" y="{fy}" font-family="{MONO}" font-size="{fs}" fill="#7d8590" '
             f'textLength="{len(prompt.rstrip()) * cw:.1f}" lengthAdjust="spacingAndGlyphs">{escape(prompt.rstrip())}</text>')
    nx = PAD_X + len(prompt) * cw
    o.append(f'<clipPath id="nm"><rect x="{nx:.1f}" y="{fy - 12}" height="16" width="{len(name) * cw if STATIC else 0}">'
             + ("" if STATIC else f'<animate attributeName="width" calcMode="discrete" begin="{end:.2f}s" '
                                  f'dur="{len(name) * 0.07:.2f}s" fill="freeze" '
                                  f'values="{";".join(f"{k * cw:.1f}" for k in range(len(name) + 1))}"/>')
             + '</rect></clipPath>')
    o.append(f'<text x="{nx:.1f}" y="{fy}" font-family="{MONO}" font-size="{fs}" font-weight="700" fill="#e6edf3" '
             f'textLength="{len(name) * cw:.1f}" lengthAdjust="spacingAndGlyphs" clip-path="url(#nm)">{escape(name)}</text>')
    cx = nx + len(name) * cw + 3
    o.append(f'<rect x="{cx:.1f}" y="{fy - 10}" width="{cw:.1f}" height="13" fill="#e6edf3">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" '
             f'repeatCount="indefinite"/></rect>')
    o.append('</svg>')
    return "\n".join(o)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    lines = to_ascii(*prep(src))
    open(dst, "w").write(svg(lines))
    print(f"wrote {dst}: {len(lines)} rows x {COLS} cols")
