"""Dev tool: montage of PNG files into one contact sheet.

    python -m games.marioparty.sheet <out.png> <cols> <cell width> <png>...
"""
import os
import sys

from PIL import Image, ImageDraw


def montage(out, cols, cw, paths, labels=None):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ch = max(int(im.height * cw / im.width) for im in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (ch + 12)), (24, 24, 28))
    dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = (i % cols) * cw, (i // cols) * (ch + 12)
        sheet.paste(im.resize((cw, int(im.height * cw / im.width))), (x, y + 12))
        dr.text((x + 2, y), (labels[i] if labels else os.path.basename(paths[i]))[:cw // 6], fill=(255, 255, 0))
    sheet.save(out)
    print(f"sheet: {out} {sheet.size} ({len(ims)} images)")


if __name__ == "__main__":
    montage(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:])
