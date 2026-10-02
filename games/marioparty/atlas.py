"""DIRTY ROOM dev tool: contact sheet of MainFS images, retail next to clean, to decide what needs a brief.

    python -m games.marioparty.atlas <retail rom> <clean rom> <out.png> <dir>[/<file>[-<file>]] [--cell 72] [--max 160]
        [--zoom]   retail only, with quarter lines (for writing a brief in normalised coordinates)

Each cell: retail (left) and clean (right), label "file/key WxH mode". Output goes to the work dir, never the repo.
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

from . import images, mainfs


def _fit(rgba, cell):
    im = Image.fromarray(rgba, "RGBA")
    bg = Image.new("RGBA", im.size, (70, 70, 90, 255))
    bg.alpha_composite(im)
    s = min(cell / im.width, cell / im.height)
    return bg.convert("RGB").resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                                    Image.NEAREST if s >= 1 else Image.BILINEAR)


def main(argv):
    retail, clean, out, sel = argv[1], argv[2], argv[3], argv[4]
    cell = int(argv[argv.index("--cell") + 1]) if "--cell" in argv else 72
    limit = int(argv[argv.index("--max") + 1]) if "--max" in argv else 160
    d, _, fr = sel.partition("/")
    lo, _, hi = fr.partition("-")
    d, lo = int(d), int(lo) if lo else 0
    hi = int(hi) if hi else (lo if fr else 10 ** 6)
    rd = mainfs.read(open(retail, "rb").read())[d]
    cd = mainfs.read(open(clean, "rb").read())[d]
    cells = []
    for f in range(lo, min(hi, len(rd) - 1) + 1):
        a, b = images.find(rd[f]["raw"]) or [], images.find(cd[f]["raw"]) or []
        for x, y in zip(a, b):
            cells.append((f"{f}/{x.key} {x.w}x{x.h} {x.mode}", x.rgba, y.rgba))
    total = len(cells)
    cells = cells[:limit]
    zoom = "--zoom" in argv
    if zoom:
        cols = max(1, 1600 // (cell + 6))
        rows = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (cell + 6), rows * (cell + 12)), (24, 24, 28))
        dr = ImageDraw.Draw(sheet)
        for i, (label, a, b) in enumerate(cells):
            x, y = (i % cols) * (cell + 6), (i // cols) * (cell + 12)
            dr.text((x + 1, y), label[:cell // 6], fill=(255, 255, 0))
            im = _fit(a, cell)
            sheet.paste(im, (x, y + 11))
            for q in (0.25, 0.5, 0.75):
                c = (0, 255, 255) if q == 0.5 else (0, 150, 150)
                dr.line([(x + im.width * q, y + 11), (x + im.width * q, y + 11 + im.height)], fill=c)
                dr.line([(x, y + 11 + im.height * q), (x + im.width, y + 11 + im.height * q)], fill=c)
        sheet.save(out)
        print(f"atlas: {out} {sheet.size}, {len(cells)} of {total} images of dir {d} (retail, zoom)")
        return
    cols = max(1, min(8, 1600 // (2 * cell + 8)))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (2 * cell + 8), rows * (cell + 12)), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    for i, (label, a, b) in enumerate(cells):
        x, y = (i % cols) * (2 * cell + 8), (i // cols) * (cell + 12)
        dr.text((x + 1, y), label[:(2 * cell) // 6], fill=(255, 255, 0))
        sheet.paste(_fit(a, cell), (x, y + 11))
        sheet.paste(_fit(b, cell), (x + cell + 2, y + 11))
    sheet.save(out)
    print(f"atlas: {out} {sheet.size}, {len(cells)} of {total} images of dir {d}")


if __name__ == "__main__":
    main(sys.argv)
