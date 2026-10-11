"""
Static, animated contribution heatmap -> assets/contrib-heatmap.svg
(+ data/contributions.json, which the info card reads so its stats match).

  python scripts/make_heatmap.py            # STATIC=1 for a frozen frame
Numbers come from profile.json -> heatmap.
"""
import datetime as dt
import json
import os
import random

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATIC = os.environ.get("STATIC") == "1"

import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import load  # noqa: E402

_CFG = load()["heatmap"]
TOTAL = int(_CFG["total"])         # contributions shown for the year (profile.json -> heatmap.total)
SEED = int(_CFG["seed"])           # change for a different pattern
END = _CFG["end"]                  # last day on the graph (profile.json -> heatmap.end_date, blank = today)
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#7cffcb"]  # neon top end
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


def make_data():
    rnd = random.Random(SEED)
    start = END - dt.timedelta(days=END.weekday() + 1 + 52 * 7)   # a Sunday, 53 columns back
    n = (END - start).days + 1
    sprint = (n - 150, n - 106)                                       # one long focused streak in spring
    days, energy = [], 0.8
    for i in range(n):
        d = start + dt.timedelta(days=i)
        energy = min(1.5, max(0.35, energy + rnd.uniform(-0.15, 0.15)))   # slow busy/quiet drift
        weekday = d.weekday() < 5
        forced = sprint[0] <= i < sprint[1] or i >= n - 17              # keeps streaks believable
        p_active = 1 if forced else (0.86 if weekday else 0.5) * min(1, energy + 0.2)
        w = (0.4 + rnd.expovariate(1 / energy)) * (1 if weekday else 0.6) if rnd.random() < p_active else 0
        days.append([d, w])
    s = sum(w for _, w in days)
    counts = [round(w / s * TOTAL) if w else 0 for _, w in days]
    counts = [max(1, c) if w else 0 for c, (_, w) in zip(counts, days)]
    # land exactly on TOTAL: add to the busiest days, or trim them (never below 1);
    # if every active day is already 1, switch off the quietest days instead
    while sum(counts) != TOTAL:
        diff = TOTAL - sum(counts)
        order = sorted((i for i, c in enumerate(counts) if c), key=lambda i: -counts[i])
        if diff > 0:
            for i in order[:diff]:
                counts[i] += 1
        else:
            big = [i for i in order if counts[i] > 1][:-diff]
            if big:
                for i in big:
                    counts[i] -= 1
            else:
                for i in sorted(order, key=lambda i: days[i][1])[:-diff]:
                    counts[i] = 0
    return [(d, c) for (d, _), c in zip(days, counts)]


def stats(data):
    longest = cur = 0
    for _, c in data:
        cur = cur + 1 if c else 0
        longest = max(longest, cur)
    current = 0
    for _, c in reversed(data):
        if not c:
            break
        current += 1
    best_d, best_c = max(data, key=lambda x: x[1])
    return {"total": sum(c for _, c in data), "longest_streak": longest, "current_streak": current,
            "best_day": best_c, "best_day_date": best_d.isoformat(),
            "active_days": sum(1 for _, c in data if c)}


def level(c, mx):
    if c == 0:
        return 0
    q = c / mx
    return 1 if q < .15 else 2 if q < .32 else 3 if q < .55 else 4 if q < .8 else 5


def svg(data, st):
    CELL, GAP = 12, 3.2
    LX, TY = 44, 30                                   # room for weekday / month labels
    weeks = (len(data) + 6) // 7
    W = 860
    H = TY + 7 * (CELL + GAP) + 58
    mx = sorted(c for _, c in data)[int(len(data) * 0.97)] or 1
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">',
         '<style>',
         '.l{fill:#7d8590;font-size:11.5px;font-weight:600}',
         '.c{transform-box:fill-box;transform-origin:center}',
         '' if STATIC else '.c{opacity:0;animation:in .5s cubic-bezier(.2,.9,.3,1.3) forwards}'
                           '@keyframes in{0%{opacity:0;transform:translateY(-6px) scale(.3)}'
                           '100%{opacity:1;transform:none}}'
                           '.hot{animation:in .5s cubic-bezier(.2,.9,.3,1.3) forwards,glow 1.4s ease-out forwards}'
                           '@keyframes glow{0%,40%{filter:none}60%{filter:drop-shadow(0 0 4px #7cffcb)}100%{filter:none}}',
         '</style>',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>']

    # month labels at the first column whose week contains the 1st
    last = None
    for w in range(weeks):
        d = data[w * 7][0]
        for k in range(7):
            if w * 7 + k < len(data) and data[w * 7 + k][0].day == 1:
                d = data[w * 7 + k][0]
        if d.month != last and (w == 0 or d.day <= 7):
            o.append(f'<text class="l" x="{LX + w * (CELL + GAP)}" y="{TY - 9}">{d.strftime("%b")}</text>')
            last = d.month
    for k, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o.append(f'<text class="l" x="{LX - 8}" y="{TY + k * (CELL + GAP) + 9.5}" text-anchor="end">{name}</text>')

    for i, (d, c) in enumerate(data):
        w, k = divmod(i, 7)
        lv = level(c, mx)
        delay = 0.15 + w * 0.022 + k * 0.035                     # diagonal sweep
        cls = "c hot" if lv == 5 else "c"
        style = "" if STATIC else f' style="animation-delay:{delay:.2f}s"'
        o.append(f'<rect class="{cls}"{style} x="{LX + w * (CELL + GAP):.1f}" y="{TY + k * (CELL + GAP):.1f}" '
                 f'width="{CELL}" height="{CELL}" rx="2.5" fill="{LEVELS[lv]}"><title>{c} on {d:%b %d}</title></rect>')

    fy = TY + 7 * (CELL + GAP) + 22
    o.append(f'<text x="{LX}" y="{fy}" font-size="14" font-weight="700" fill="#e6edf3">{st["total"]:,} contributions'
             f'<tspan fill="#7d8590" font-weight="500"> in the last year</tspan></text>')
    o.append(f'<text x="{LX}" y="{fy + 20}" font-size="12" fill="#7d8590">'
             f'Longest streak <tspan fill="#7cffcb" font-weight="700">{st["longest_streak"]} days</tspan>'
             f'   ·   Current streak <tspan fill="#7cffcb" font-weight="700">{st["current_streak"]} days</tspan>'
             f'   ·   Best day <tspan fill="#7cffcb" font-weight="700">{st["best_day"]}</tspan></text>')
    lx = W - 22 - 6 * (CELL + 3) - 34
    o.append(f'<text class="l" x="{lx - 6}" y="{fy}" text-anchor="end">Less</text>')
    for n, col in enumerate(LEVELS):
        o.append(f'<rect x="{lx + n * (CELL + 3)}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}"/>')
    o.append(f'<text class="l" x="{lx + 6 * (CELL + 3) + 3}" y="{fy}">More</text>')
    o.append('</svg>')
    return "\n".join(o)


if __name__ == "__main__":
    data = make_data()
    st = stats(data)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    json.dump({"stats": st, "days": [[d.isoformat(), c] for d, c in data]},
              open(os.path.join(ROOT, "data", "contributions.json"), "w"), indent=1)
    open(os.path.join(ROOT, "assets", "contrib-heatmap.svg"), "w").write(svg(data, st))
    print("wrote assets/contrib-heatmap.svg", st)
