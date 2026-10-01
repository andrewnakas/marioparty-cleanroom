"""DIRTY ROOM: retail ROM -> spec (coarse facts only).

    python -m games.marioparty.extract_spec <retail rom> [tex]

Textures (every image in MainFS): format/size, 4x4 colour grid (16x16 from 128 px), 2-bit alpha outline.
For intensity images the outline is the 2-bit intensity (they are masks / glyphs: the value is the alpha).
"""
import json
import os
import sys

import numpy as np

from cleanroom.decomp import spec as S
from . import images, mainfs

SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec")


def fact(im):
    n = 16 if max(im.w, im.h) >= 128 else 4
    d = {"w": im.w, "h": im.h, "mode": im.mode, "grid": S.grid(im.rgba, n)}
    a = im.rgba[..., 3]
    if im.mode in ("i", "ia") or (a < 250).any():
        d["alpha2"] = S.alpha2(a)
    return d


def textures(rom):
    out, kinds, skipped = {}, {}, []
    for d, files in enumerate(mainfs.read(rom)):
        for f, e in enumerate(files):
            k = images.kind(e["raw"])
            kinds[k] = kinds.get(k, 0) + 1
            try:
                ims = images.find(e["raw"])
            except ValueError as err:
                skipped.append(f"{d}/{f}: {err}")
                continue
            for im in ims or ():
                out[f"{d}/{f}/{im.key}"] = fact(im)
    return out, kinds, skipped


def main(argv):
    rom = open(argv[1], "rb").read()
    os.makedirs(SPEC, exist_ok=True)
    tex, kinds, skipped = textures(rom)
    json.dump(tex, open(os.path.join(SPEC, "textures.json"), "w"), separators=(",", ":"))
    px = sum(t["w"] * t["h"] for t in tex.values())
    print(f"textures: {len(tex)} images, {px / 1e6:.1f} Mpx, files by kind {kinds}")
    print(f"skipped {len(skipped)}:", "; ".join(skipped[:8]))


if __name__ == "__main__":
    main(sys.argv)
