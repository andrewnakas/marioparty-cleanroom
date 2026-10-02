"""DIRTY ROOM: retail ROM -> spec (coarse facts only).

    python -m games.marioparty.extract_spec <retail rom> [tex|hvq|snd]

Textures (every image in MainFS): format/size, 4x4 colour grid (16x16 from 128 px), 2-bit alpha outline.
For intensity images the outline is the 2-bit intensity (they are masks / glyphs: the value is the alpha).
"""
import json
import os
import sys

import numpy as np

from cleanroom.decomp import spec as S
from . import audio, hvqfs, images, mainfs

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


def _rgb_grid(rgba, n):
    return bytes(v for cell in S.grid(rgba, n) for v in cell[:3]).hex()


def pictures(rom):
    """Pre-rendered pictures (HVQ2 in retail, decoded once by hvq_dirty): 4x4 colour grid per 64x48 tile,
    16x16 for the 160x128 stills. The grid is the only thing that leaves the dirty room."""
    import struct
    from . import hvq_dirty
    bg = []
    for b, files in enumerate(hvqfs.read(rom)):
        tw, th, nx, ny = struct.unpack_from(">4I", files[0])
        tiles = hvq_dirty.bg(b)
        assert len(tiles) == len(files) - 1 and tiles.shape[1:3] == (th, tw)
        bg.append({"tw": tw, "th": th, "nx": nx, "ny": ny, "tiles": len(tiles),
                   "grid": "".join(_rgb_grid(t, 4) for t in tiles)})
    fs = {}
    for d, files in enumerate(mainfs.read(rom)):
        for f, e in enumerate(files):
            if e["raw"][:4] == b"HVQ ":
                im = hvq_dirty.fs(d, f)
                fs[f"{d}/{f}"] = {"w": im.shape[1], "h": im.shape[0], "grid": _rgb_grid(im, 16)}
    return {"bg": bg, "fs": fs}


def samples(rom):
    """Every wave: length, analysis rate, loop points, coarse spectral outline, median pitch."""
    from cleanroom.audio import descriptor
    from cleanroom.audio.pitch import median_f0
    out = {}
    for w in audio.waves(rom):
        pcm = audio.decode(rom, w).astype(np.float64)
        rate = w["rate"] or audio.SFX_RATE
        d = {"n": len(pcm), "rate": rate, "desc": descriptor.describe(pcm, rate)}
        f0 = median_f0((pcm[:rate] / 32768).astype(np.float32), rate) if len(pcm) > 2048 else None
        if f0:
            d["f0"] = round(f0, 1)
        if w["loop"]:
            d["loop"] = [w["loop"]["start"], w["loop"]["end"], w["loop"]["count"]]
        out[w["name"]] = d
    return out


def main(argv):
    rom = open(argv[1], "rb").read()
    os.makedirs(SPEC, exist_ok=True)
    what = argv[2] if len(argv) > 2 else "tex"
    if what == "snd":
        smp = samples(rom)
        json.dump(smp, open(os.path.join(SPEC, "samples.json"), "w"), separators=(",", ":"))
        print(f"samples: {len(smp)} waves, {sum(d['n'] for d in smp.values()) / 1e6:.1f} M samples, "
              f"{sum(1 for d in smp.values() if 'f0' in d)} pitched, {sum(1 for d in smp.values() if 'loop' in d)} looped")
        return
    if what == "hvq":
        pic = pictures(rom)
        json.dump(pic, open(os.path.join(SPEC, "pictures.json"), "w"), separators=(",", ":"))
        print(f"pictures: {len(pic['bg'])} backgrounds, {sum(b['tiles'] for b in pic['bg'])} tiles, {len(pic['fs'])} stills")
        return
    tex, kinds, skipped = textures(rom)
    json.dump(tex, open(os.path.join(SPEC, "textures.json"), "w"), separators=(",", ":"))
    px = sum(t["w"] * t["h"] for t in tex.values())
    print(f"textures: {len(tex)} images, {px / 1e6:.1f} Mpx, files by kind {kinds}")
    print(f"skipped {len(skipped)}:", "; ".join(skipped[:8]))


if __name__ == "__main__":
    main(sys.argv)
