"""
Build the terminal-style ASCII portrait SVG from braille-pattern text art
(U+2800-U+28FF), rendering each dot as an actual vector rect instead of
relying on a font to draw the braille glyphs. Font-based rendering of
braille characters is unreliable across renderers (glyph alignment/spacing
varies), which visibly warps the art -- drawing the dots ourselves guarantees
a pixel-exact reproduction of the source art.

Reuses the same frame + row-by-row "typing" reveal animation as
make_ascii_svg.py / make_ascii_svg_from_text.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "new-ascii.txt")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "avi-ascii.svg")

DOT = 4  # px per braille dot
CELL_W = DOT * 2  # each braille char is 2 dots wide
CELL_H = DOT * 4  # ... and 4 dots tall

PAD = 20
TITLEBAR_H = 30
STATUS_H = 30

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"
CURSOR = "#c9d1d9"

ROW_DUR = 0.11
STAGGER = 0.11

# bit -> (dx, dy) within the 2x4 braille dot cell
DOT_BITS = [(0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04),
            (1, 0, 0x08), (1, 1, 0x10), (1, 2, 0x20),
            (0, 3, 0x40), (1, 3, 0x80)]

with open(SRC, encoding="utf-8") as f:
    rows_txt = f.read().splitlines()
rows_txt = [r for r in rows_txt if r != ""] or rows_txt
COLS = max(len(r) for r in rows_txt)
ROWS = len(rows_txt)

ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

STATIC = bool(os.environ.get("STATIC"))

art_top = TITLEBAR_H + PAD * 0.35


def row_dots(line):
    """4 rows (dy 0..3) of booleans, each COLS*2 wide (dx 0/1 per char)."""
    grid = [[False] * (COLS * 2) for _ in range(4)]
    for cx, ch in enumerate(line):
        cp = ord(ch)
        if not (0x2800 <= cp <= 0x28FF):
            continue
        bits = cp - 0x2800
        for dx, dy, bit in DOT_BITS:
            if bits & bit:
                grid[dy][cx * 2 + dx] = True
    return grid


def rle_rects(bools, y, dot_size):
    """Run-length-encode a row of booleans into (x, width) rects."""
    rects = []
    start = None
    for i, on in enumerate(bools):
        if on and start is None:
            start = i
        elif not on and start is not None:
            rects.append((start, i - start))
            start = None
    if start is not None:
        rects.append((start, len(bools) - start))
    return rects


parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append('<defs>'
             f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
             f'</linearGradient></defs>')

parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1}" height="{CANVAS_H-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{CANVAS_W/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">riveroangelsebas@github: ~$ ./portrait.sh</text>')

for ry, line in enumerate(rows_txt):
    row_top = art_top + ry * CELL_H
    delay = ry * STAGGER
    grid = row_dots(line)

    art_rects = []
    for dy in range(4):
        y = row_top + dy * DOT
        for start, length in rle_rects(grid[dy], y, DOT):
            x = PAD + start * DOT
            w = length * DOT
            art_rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{DOT}" fill="{INK}"/>')
    art_markup = "".join(art_rects)

    if STATIC:
        parts.append(art_markup)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_top:.1f}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{art_markup}</g>')
    parts.append(
        f'<rect y="{row_top+1:.1f}" width="{CELL_W}" height="{CELL_H-2}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD+ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay+ROW_DUR:.3f}s"/></rect>'
    )

status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'riveroangelsebas@github:~$ whoami <tspan fill="{INK}">riveroangelsebas</tspan></text>')
parts.append(f'<rect x="{PAD+288}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" repeatCount="indefinite"/></rect>')

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", CANVAS_W, "x", CANVAS_H, "; grid", COLS, "x", ROWS)
