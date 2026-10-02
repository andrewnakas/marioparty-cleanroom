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
from . import hvqfs, images, mainfs, romtool

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


def _smooth(grid, w, h):
    """Colour grid (gh, gw, 3) -> RGBA (h, w, 4): bilinear upsample, then a small blur to hide the lattice."""
    gh, gw = grid.shape[:2]
    ys = np.clip((np.arange(h) + 0.5) / h * gh - 0.5, 0, gh - 1)
    xs = np.clip((np.arange(w) + 0.5) / w * gw - 0.5, 0, gw - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, gh - 1), np.minimum(x0 + 1, gw - 1)
    fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    g = grid.astype(np.float32)
    im = (g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx) * (1 - fy) + (g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx) * fy
    return np.dstack([np.clip(im, 0, 255), np.full((h, w), 255, np.float32)]).astype(np.uint8)


def background(b, d):
    """One pre-rendered background -> RGBA (ny*th, nx*tw, 4), top row first (None if it is not a full mosaic)."""
    tw, th, nx, ny, n = d["tw"], d["th"], d["nx"], d["ny"], d["tiles"]
    g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(n, 4, 4, 3)
    if n != nx * ny:
        return None
    # tiles are stored bottom row first
    mosaic = g.reshape(ny, nx, 4, 4, 3)[::-1].transpose(0, 2, 1, 3, 4).reshape(ny * 4, nx * 4, 3)
    return _smooth(mosaic, nx * tw, ny * th)


def background_tiles(b, d, hooks=()):
    """-> list of CRQ1 files in container order."""
    tw, th, nx, ny, n = d["tw"], d["th"], d["nx"], d["ny"], d["tiles"]
    im = None
    for hook in hooks:
        im = hook(f"bg/{b}", d)
        if im is not None:
            break
    if im is None:
        im = background(b, d)
    if im is None:
        g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(n, 4, 4, 3)
        return [hvqfs.crq(hvqfs.rgba5551(_smooth(t, tw, th))) for t in g]
    px = hvqfs.rgba5551(im)
    return [hvqfs.crq(px[(ny - 1 - k // nx) * th:(ny - k // nx) * th, (k % nx) * tw:(k % nx + 1) * tw]) for k in range(n)]


def still(key, d):
    g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(16, 16, 3)
    return _smooth(g, d["w"], d["h"])


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
    pic = json.load(open(os.path.join(SPEC, "pictures.json")))
    dirs = mainfs.read(retail)
    n = 0
    for d, files in enumerate(dirs):
        for f, e in enumerate(files):
            if e["raw"][:4] == b"HVQ ":
                key, out = f"{d}/{f}", None
                for hook in hooks:
                    out = hook("still/" + key, pic["fs"][key])
                    if out is not None:
                        break
                e["raw"] = hvqfs.crq(hvqfs.rgba5551(still(key, pic["fs"][key]) if out is None else out))
                e["comp"] = None
                n += 1
                continue
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
    bgs = hvqfs.read(retail)
    for k, d in enumerate(pic["bg"]):
        bgs[k][1:] = background_tiles(k, d, hooks)
        n += d["tiles"]
    b.put_hvqfs(bgs)
    b.put_decoder()
    return b, n


def main(argv):
    retail = open(argv[1], "rb").read()
    assert hashlib.sha1(retail).hexdigest() == romtool.RETAIL_SHA1, "not the USA ROM the tools were written for"
    b, n = build(retail)
    out = b.finish()
    open(argv[2], "wb").write(out)
    print(f"generate: {n} pictures regenerated; " + "; ".join(b.log))
    print(f"rom: {argv[2]} {len(out) >> 20} MB sha1 {hashlib.sha1(out).hexdigest()[:12]}")


if __name__ == "__main__":
    main(sys.argv)
