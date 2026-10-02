"""CLEAN ROOM: spec -> clean ROM.

    python -m games.marioparty.generate <retail rom> <out.z64>

The retail image supplies the program and the container layouts (kept facts); every pixel payload, palette and sound sample
is overwritten with data made from `spec/` only. `taint.py` proves it.
"""
import hashlib
import json
import os
import sys

import numpy as np

from cleanroom.audio import descriptor
from cleanroom.decomp import gen as G
from . import audio, briefs, hvqfs, images, mainfs, romtool

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
LEVELS = np.array([0, 85, 170, 255], np.float32)


# Pictures whose default rendering still repeated a retail window run by chance (taint report feedback: one bit per
# picture, no retail content): rendered with 8 levels per channel instead of 16.
COARSE = {"8/14/p0", "31/15/p1"}


def _blur(a):
    p = np.pad(a.astype(np.float32), 1, mode="edge")
    return (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + 4 * p[1:-1, 1:-1]) / 8


def texture(key, d):
    """RGBA uint8 from one spec entry."""
    w, h, mode = d["w"], d["h"], d["mode"]
    rgba = G.from_digest(key, d)
    if mode == "i":            # mask / glyph: the 2-bit outline is the picture
        v = _blur(G.unpack_alpha2(d["alpha2"], w, h))
        # our own grain on the soft part (the flat black and white of a mask stay flat)
        soft = (v > 4) & (v < 251)
        v = np.where(soft, v * G.detail(G.h32("grain", key), w, h, 0.12, 2.0), v)
        v = np.clip(v, 0, 255).astype(np.uint8)
        rgba = np.dstack([v, v, v, v])
    elif mode == "rgba1" and key in COARSE:
        rgba[..., :3] = (rgba[..., :3] >> 5) * 36                    # 8 levels: see COARSE
    elif mode == "rgba1":
        # 16-bit and palette pictures: 16 levels per channel. A smooth 5-bit ramp repeats the 4-pixel windows of
        # any other smooth ramp of the same hue (measured with taint_lab: 138 chance hits); 4-bit steps do not.
        rgba[..., :3] = (rgba[..., :3] >> 4) * 17
    if mode == "ia":
        v = rgba[..., :3].astype(np.float32).mean(2).astype(np.uint8)
        rgba = np.dstack([v, v, v, rgba[..., 3]])
    elif mode == "rgb":
        rgba[..., 3] = 255
    return np.ascontiguousarray(rgba)


CELL = 3      # backgrounds: lattice point every 8 px (the kept grid is one colour per 16x12 px)


def _lattice(grid, w, h, k):
    """Colour grid (gh, gw, 3) for a w x h picture -> RGB lattice ((h >> k) + 1, (w >> k) + 1, 3): the grid
    smoothly interpolated at every (1 << k)-th pixel corner. The decoder interpolates between lattice points."""
    gh, gw = grid.shape[:2]
    ys = np.clip(np.arange((h >> k) + 1) * (1 << k) / h * gh - 0.5, 0, gh - 1)
    xs = np.clip(np.arange((w >> k) + 1) * (1 << k) / w * gw - 0.5, 0, gw - 1)
    y0, x0 = np.minimum(np.floor(ys).astype(int), gh - 1), np.minimum(np.floor(xs).astype(int), gw - 1)
    y1, x1 = np.minimum(y0 + 1, gh - 1), np.minimum(x0 + 1, gw - 1)
    fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    g = grid.astype(np.float32)
    im = (g[y0][:, x0] * (1 - fx) + g[y0][:, x1] * fx) * (1 - fy) + (g[y1][:, x0] * (1 - fx) + g[y1][:, x1] * fx) * fy
    return np.clip(np.round(im), 0, 255).astype(np.uint8)


def _picture(im):
    """Hook output (RGBA, full resolution) -> CRQ1 file."""
    return hvqfs.crq(hvqfs.rgba5551(im))


def background_tiles(b, d, hooks=()):
    """One pre-rendered background -> its tile files in container order (rows bottom to top).

    Default: the kept grid as one smooth picture across the whole mosaic. A hook may return a full RGBA picture
    (ny*th, nx*tw, 4), top row first."""
    tw, th, nx, ny, n = d["tw"], d["th"], d["nx"], d["ny"], d["tiles"]
    g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(n, 4, 4, 3)
    for hook in hooks:
        im = hook(f"bg/{b}", d)
        if im is not None:
            return [_picture(im[(ny - 1 - k // nx) * th:(ny - k // nx) * th, (k % nx) * tw:(k % nx + 1) * tw])
                    for k in range(n)]
    if n != nx * ny:
        return [hvqfs.crq_smooth(_lattice(t, tw, th, CELL), tw, th, CELL) for t in g]
    mosaic = g.reshape(ny, nx, 4, 4, 3)[::-1].transpose(0, 2, 1, 3, 4).reshape(ny * 4, nx * 4, 3)
    lat = _lattice(mosaic, nx * tw, ny * th, CELL)
    sx, sy = tw >> CELL, th >> CELL
    out = []
    for k in range(n):
        r, c = ny - 1 - k // nx, k % nx
        out.append(hvqfs.crq_smooth(lat[r * sy:(r + 1) * sy + 1, c * sx:(c + 1) * sx + 1], tw, th, CELL))
    return out


def still(key, d):
    """160x128 stills: 16x16 kept grid, lattice every 4 px."""
    g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(16, 16, 3)
    return hvqfs.crq_smooth(_lattice(g, d["w"], d["h"], 2), d["w"], d["h"], 2)


def sample(name, d):
    """One wave (int16, d["n"] samples) resynthesised from its outline.

    Pitched sounds get one steady pitch (the spec's median f0). For a looped tone the pitch is snapped so the
    loop holds a whole number of periods: that is what the engine plays, and it keeps instruments in tune."""
    n, rate = d["n"], d["rate"]
    frames = [dict(f) for f in d["desc"]["frames"]]
    tonal = [f for f in frames if f["f0"] > 20 and f["h"] > 0.3]
    loop = d.get("loop")
    f0 = d.get("f0") or (float(np.median([f["f0"] for f in tonal])) if len(tonal) * 2 > len(frames) else None)
    if f0 and tonal:
        if loop and loop[1] > loop[0]:
            length = loop[1] - loop[0]
            snapped = max(1, round(length * f0 / rate)) * rate / length
            if length < 4096 or abs(np.log2(snapped / f0)) < 0.04:
                f0 = snapped
        for f in tonal:
            f["f0"] = f0
    x = descriptor.synthesize({"frames": frames}, n, rate, seed=G.h32("smp", name))
    if loop and 0 <= loop[0] < loop[1] <= n:
        x = descriptor.make_loop_seamless(x, loop[0], loop[1])
    dither = np.random.default_rng(G.h32("dither", name)).integers(-1, 2, n)
    return np.clip(np.round(np.clip(x, -1, 1) * 32000) + dither, -32768, 32767).astype(np.int16)


def put_samples(b, retail, hooks=()):
    smp = json.load(open(os.path.join(SPEC, "samples.json")))
    only = os.environ.get("MP_SND")      # dev bisecting: MP_SND=s2_0,t3 regenerates only those groups
    for w in audio.waves(retail):
        if only and not w["name"].startswith(tuple(only.split(","))):
            continue
        if _off("raw") and w["type"] != 0:
            continue
        d, pcm = smp[w["name"]], None
        for hook in hooks:
            pcm = hook("snd/" + w["name"], d)
            if pcm is not None:
                break
        audio.put(b.image, w, sample(w["name"], d) if pcm is None else pcm)
    b.log.append(f"samples {len(smp)}")
    return len(smp)


def _off(what):
    """Dev bisecting: MP_OFF=glyph,pack1b,raw32,still,bg,snd leaves those parts retail (never for a release)."""
    return what in os.environ.get("MP_OFF", "").split(",")


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


def images_of(d, f, raw, tex, hooks=()):
    """{image key: RGBA} for every image of one MainFS file (None if it holds none)."""
    ims = images.find(raw)
    if not ims:
        return None
    new = {}
    for im in ims:
        key = f"{d}/{f}/{im.key}"
        out = None
        for hook in hooks:
            out = hook(key, tex[key])
            if out is not None:
                break
        if out is not None and tex[key]["mode"] == "rgba1":
            out = out.copy()
            out[..., :3] = (out[..., :3] >> 4) * 17          # same 16 levels as the default rendering
        new[im.key] = texture(key, tex[key]) if out is None else out
    return new


def build(retail, hooks=()):
    tex = json.load(open(os.path.join(SPEC, "textures.json")))
    have_pic = os.path.exists(os.path.join(SPEC, "pictures.json"))      # absent only in dev builds
    pic = json.load(open(os.path.join(SPEC, "pictures.json"))) if have_pic else {"bg": [], "fs": {}}
    dirs = mainfs.read(retail)
    n = 0
    for d, files in enumerate(dirs):
        for f, e in enumerate(files):
            if e["raw"][:4] == b"HVQ " and have_pic and not _off("still"):
                key, out = f"{d}/{f}", None
                for hook in hooks:
                    out = hook("still/" + key, pic["fs"][key])
                    if out is not None:
                        break
                e["raw"] = still(key, pic["fs"][key]) if out is None else _picture(out)
                e["comp"] = None
                n += 1
                continue
            if (d, f) in images.GLYPH4 and not _off("glyph"):
                g = tex[f"{d}/{f}/glyphs"]
                lv = (G.unpack_alpha2(g["alpha2"], g["w"], 1) / 85).astype(np.uint8).ravel()
                e["raw"], e["comp"] = images.glyph_rebuild(e["raw"], images.GLYPH4[(d, f)], lv), None
                n += 1
                continue
            if not _selected(d, f, images.kind(e["raw"])):
                continue
            if (_off("pack1b") and e["raw"][:4] == bytes([0, 0, 0, 0x1B])) or (_off("raw32") and images.kind(e["raw"]) == "raw32"):
                continue
            new = images_of(d, f, e["raw"], tex, hooks)
            if new is None:
                continue
            n += len(new)
            e["raw"] = images.rebuild(e["raw"], new)
            e["comp"] = None
    for d, f in images.KEPT_2BIT:            # kept as it is, but stored by our own encoder like everything else
        dirs[d][f]["comp"] = None
    b = romtool.Builder(retail)
    b.put_mainfs(dirs)
    if have_pic and not _off("bg"):
        bgs = hvqfs.read(retail)
        for k, d in enumerate(pic["bg"]):
            bgs[k][1:] = background_tiles(k, d, hooks)
            n += d["tiles"]
        b.put_hvqfs(bgs)
    else:
        b.image[hvqfs.ROM_OFFSET:hvqfs.ROM_END] = retail[hvqfs.ROM_OFFSET:hvqfs.ROM_END]
    b.put_decoder()
    if not _off("snd"):
        n += put_samples(b, retail, hooks)
    if os.environ.get("MP_OFF"):
        b.log.append("DEV BUILD, retail parts: " + os.environ["MP_OFF"])
    return b, n


def main(argv):
    retail = open(argv[1], "rb").read()
    assert hashlib.sha1(retail).hexdigest() == romtool.RETAIL_SHA1, "not the USA ROM the tools were written for"
    from . import voices
    b, n = build(retail, hooks=(briefs.paint, voices.hook))
    out = b.finish()
    open(argv[2], "wb").write(out)
    print(f"generate: {n} pictures and sounds regenerated; " + "; ".join(b.log))
    print(f"rom: {argv[2]} {len(out) >> 20} MB sha1 {hashlib.sha1(out).hexdigest()[:12]}")


if __name__ == "__main__":
    main(sys.argv)
