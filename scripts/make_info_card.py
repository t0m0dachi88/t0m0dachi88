"""
Info card -> assets/info-card.svg   (run after make_heatmap.py and make_ascii_portrait.py)

Terminal window: name + tagline, then Now / Creating / Stack / Highlights,
then four stat tiles read from data/contributions.json so they always match the
heatmap. Every block fades and slides in on a stagger, once.
  python scripts/make_info_card.py          # STATIC=1 for a frozen frame
"""
import json
import os
import re
from xml.sax.saxutils import escape

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATIC = os.environ.get("STATIC") == "1"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import load  # noqa: E402

CFG = load()
NAME = CFG["name"]
TAGLINE = CFG["tagline"]
NOW = (CFG["now"]["role"], CFG["now"]["where"])
CREATING = CFG["creating"]
STACK = CFG["stack"]
HIGHLIGHTS = CFG["highlights"]
HANDLE = CFG["handle"]
W = 490


def stats():
    st = json.load(open(os.environ.get("CONTRIB_JSON") or os.path.join(ROOT, "data", "contributions.json")))["stats"]
    return [(f'{st["total"]:,}', "contributions"), (f'{st["longest_streak"]}d', "longest streak"),
            (f'{st["current_streak"]}d', "current streak"), (str(st["active_days"]), "active days")]


def card(H):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{SANS}">',
         '<style>',
         '.k{fill:#7d8590;font:600 10.5px ' + MONO + ';letter-spacing:1.5px}',
         '.v{fill:#e6edf3;font-size:14px}',
         '.b{transform-box:fill-box}' if STATIC else
         '.b{opacity:0;animation:up .55s cubic-bezier(.2,.8,.2,1) forwards}'
         '@keyframes up{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}',
         '</style>',
         '<defs><linearGradient id="acc" x1="0" x2="1"><stop offset="0" stop-color="#7cffcb"/>'
         '<stop offset="1" stop-color="#5ee7ff"/></linearGradient></defs>',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>',
         f'<path d="M12 .5h{W - 24}a11.5 11.5 0 0 1 11.5 11.5v16H.5V12A11.5 11.5 0 0 1 12 .5z" fill="#161b22"/>',
         f'<line x1="1" y1="28.5" x2="{W - 1}" y2="28.5" stroke="#30363d"/>']
    for k, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        o.append(f'<circle cx="{18 + k * 16}" cy="14.5" r="5" fill="{col}"/>')
    o.append(f'<text x="{W / 2}" y="18.5" text-anchor="middle" font-family="{MONO}" font-size="11" fill="#7d8590">'
             f'{escape(HANDLE)}@github: ~$ cat about.md</text>')

    n = [0]

    def block(inner):
        style = "" if STATIC else f' style="animation-delay:{0.35 + n[0] * 0.14:.2f}s"'
        n[0] += 1
        return f'<g class="b"{style}>{inner}</g>'

    X = 26
    y = 66
    o.append(block(f'<text x="{X}" y="{y}" font-size="23" font-weight="700" fill="#e6edf3">{escape(NAME)}</text>'
                   f'<text x="{X}" y="{y + 22}" font-size="13" fill="#7d8590">{escape(TAGLINE)}</text>'))
    y += 40
    o.append(block(f'<rect x="{X}" y="{y}" width="{W - 2 * X}" height="1" fill="#30363d"/>'))

    def label(t, yy):
        return f'<rect x="{X}" y="{yy - 8.5}" width="3" height="10" rx="1" fill="url(#acc)"/>' \
               f'<text class="k" x="{X + 10}" y="{yy}">{t}</text>'

    y += 30
    o.append(block(label("NOW", y) + f'<text class="v" x="{X}" y="{y + 21}"><tspan font-weight="700">{escape(NOW[0])}</tspan>'
                   f'<tspan fill="#7cffcb" font-weight="600"> {escape(NOW[1])}</tspan></text>'))
    y += 48
    o.append(block(label("CREATING", y) + f'<text class="v" x="{X}" y="{y + 21}">{escape(CREATING)}</text>'))
    y += 48

    # stack chips, wrapped
    chips, cx, cy = [], X, y + 10
    for t in STACK:
        w = len(t) * 6.9 + 18
        if cx + w > W - X:
            cx, cy = X, cy + 27
        chips.append(f'<rect x="{cx:.1f}" y="{cy}" width="{w:.1f}" height="21" rx="10.5" fill="#161b22" stroke="#30363d"/>'
                     f'<text x="{cx + w / 2:.1f}" y="{cy + 14.5}" text-anchor="middle" font-family="{MONO}" '
                     f'font-size="11.5" fill="#c9d1d9">{escape(t)}</text>')
        cx += w + 7
    o.append(block(label("STACK", y) + "".join(chips)))
    y = cy + 21 + 30

    hl = label("HIGHLIGHTS", y)
    for i, t in enumerate(HIGHLIGHTS):
        hy = y + 22 + i * 22
        hl += f'<text x="{X}" y="{hy}" font-size="13.5"><tspan fill="#7cffcb">▸ </tspan>' \
              f'<tspan fill="#e6edf3">{escape(t)}</tspan></text>'
    o.append(block(hl))
    y += 22 + len(HIGHLIGHTS) * 22 + 12

    # stat tiles pinned to the bottom of the card
    tiles = stats()
    gap = 8
    tw = (W - 2 * X - gap * (len(tiles) - 1)) / len(tiles)
    ty = max(y, H - 22 - 58)
    for i, (num, cap) in enumerate(tiles):
        tx = X + i * (tw + gap)
        o.append(block(f'<rect x="{tx:.1f}" y="{ty}" width="{tw:.1f}" height="58" rx="8" fill="#161b22" stroke="#30363d"/>'
                       f'<text x="{tx + tw / 2:.1f}" y="{ty + 27}" text-anchor="middle" font-size="19" font-weight="700" '
                       f'fill="url(#acc)">{num}</text>'
                       f'<text x="{tx + tw / 2:.1f}" y="{ty + 45}" text-anchor="middle" font-size="10.5" '
                       f'fill="#7d8590">{cap}</text>'))
    o.append('</svg>')
    return "\n".join(o), ty + 58 + 22


if __name__ == "__main__":
    h = 470
    p = os.path.join(ROOT, "assets", "ascii-portrait.svg")
    if os.path.exists(p):
        m = re.search(r'height="(\d+)"', open(p).read())
        h = int(m.group(1)) if m else h
    svg, need = card(h)
    if need > h:                       # content taller than the portrait: grow to fit
        svg, _ = card(need)
    open(os.path.join(ROOT, "assets", "info-card.svg"), "w").write(svg)
    print("wrote assets/info-card.svg, height", max(h, need))
