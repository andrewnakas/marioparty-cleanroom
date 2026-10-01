"""CLEAN ROOM: spec -> clean ROM.

    python -m games.marioparty.generate <retail rom> <out.z64>

The retail image supplies the program and the container layouts (kept facts); every pixel payload and palette
is overwritten with data made from `spec/` only. `taint.py` proves it.
"""
import hashlib
import json
import os
import sys

import numpy as np

from cleanroom.decomp import gen as G
from . import images, mainfs, romtool

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
LEVELS = np.array([0, 85, 170, 255], np.float32)


def _blur(a):
    p = np.pad(a.astype(np.float32), 1, mode="edge")
    return (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + 4 * p[1:-1, 1:-1]) / 8


def texture(key, d):
    """RGBA uint8 from one spec entry."""
    w, h, mode = d["w"], d["h"], d["mode"]
    rgba = G.from_digest(key, d)
    if mode == "i":            # mask / glyph: the 2-bit outline is the picture
        v = np.clip(_blur(G.unpack_alpha2(d["alpha2"], w, h)), 0, 255).astype(np.uint8)
        rgba = np.dstack([v, v, v, v])
    elif mode == "ia":
        v = rgba[..., :3].astype(np.float32).mean(2).astype(np.uint8)
        rgba = np.dstack([v, v, v, rgba[..., 3]])
    elif mode == "rgb":
        rgba[..., 3] = 255
    return np.ascontiguousarray(rgba)


def _selected(d, f, kind):
    """Dev bisecting: MP_KINDS=pack,form  MP_DIRS=0-9,16  MP_SKIP=10/61,0/118 (default: everything)."""
    kinds, dirs, skip = os.environ.get("MP_KINDS"), os.environ.get("MP_DIRS"), os.environ.get("MP_SKIP", "")
    if kinds and kind not in kinds.split(","):
        return False
    if f"{d}/{f}" in skip.split(",") or f"{d}/*" in skip.split(","):
        return False
    if dirs:
        for part in dirs.split(","):
            lo, _, hi = part.partition("-")
            if int(lo) <= d <= int(hi or lo):
                return True
        return False
    return True


def build(retail, hooks=()):
    tex = json.load(open(os.path.join(SPEC, "textures.json")))
    dirs = mainfs.read(retail)
    n = 0
    for d, files in enumerate(dirs):
        for f, e in enumerate(files):
            if not _selected(d, f, images.kind(e["raw"])):
                continue
            ims = images.find(e["raw"])
            if not ims:
                continue
            new = {}
            for im in ims:
                key = f"{d}/{f}/{im.key}"
                out = None
                for hook in hooks:
                    out = hook(key, tex[key])
                    if out is not None:
                        break
                new[im.key] = texture(key, tex[key]) if out is None else out
                n += 1
            e["raw"] = images.rebuild(e["raw"], new)
            e["comp"] = None
    b = romtool.Builder(retail)
    b.put_mainfs(dirs)
    return b, n


def main(argv):
    retail = open(argv[1], "rb").read()
    assert hashlib.sha1(retail).hexdigest() == romtool.RETAIL_SHA1, "not the USA ROM the tools were written for"
    b, n = build(retail)
    out = b.finish()
    open(argv[2], "wb").write(out)
    print(f"generate: {n} textures regenerated; " + "; ".join(b.log))
    print(f"rom: {argv[2]} {len(out) >> 20} MB sha1 {hashlib.sha1(out).hexdigest()[:12]}")


if __name__ == "__main__":
    main(sys.argv)
