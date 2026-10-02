"""DIRTY ROOM dev tool: how many chance coincidences does each way of rendering the kept facts produce?

    python -m games.marioparty.taint_lab <retail rom> pic|tex

Builds the retail index once, then scores several rendering variants with the same scanner the taint report uses.
A 5-bit picture has a small alphabet, so a ramp or a dither of the same average colour easily repeats 4-pixel
windows that occur somewhere in 15 Mpx of retail pictures; this measures it instead of guessing.
"""
import json
import os
import sys

import numpy as np

from cleanroom import taint
from cleanroom.decomp import gen as G
from . import generate, hvq_dirty, hvqfs, images, mainfs, taint as T

SPEC = generate.SPEC


def decode_smooth(lat, w, h, k, mode):
    """numpy model of the CRQ2 decoder; mode: none | hash | hash3 | q<n> (keep n bits per channel, no dither)."""
    cell = 1 << k
    ys, xs = np.arange(h), np.arange(w)
    gy, gx, fy, fx = ys >> k, xs >> k, (ys & (cell - 1))[:, None, None], (xs & (cell - 1))[None, :, None]
    la = lat.astype(np.int64)
    top = la[gy][:, gx] * (cell - fx) + la[gy][:, gx + 1] * fx
    bot = la[gy + 1][:, gx] * (cell - fx) + la[gy + 1][:, gx + 1] * fx
    v = (top * (cell - fy) + bot * fy) >> (2 * k)
    X, Y = np.meshgrid(xs, ys)
    if mode == "hash":
        d = X * 0x9E5 + Y * 0x6B3
        v = v + (((d >> 3) ^ (d >> 7) ^ d) & 7)[..., None]
    elif mode == "hash3":
        for c in range(3):
            d = X * (0x9E5 + 40 * c) + Y * (0x6B3 + 22 * c) + c * 977
            d = (d >> 3) ^ (d >> 7) ^ d
            v[..., c] += (d & 15) + ((d >> 4) & 7) - 11
    bits = int(mode[1:]) if mode.startswith("q") else 5
    v = np.clip(v, 0, 255) >> (8 - bits)
    v = (v << (5 - bits)) | (v >> max(0, 2 * bits - 5)) if bits < 5 else v      # spread back to 5 bits
    out = np.empty((h, w, 4), np.uint8)
    out[..., :3] = (v & 31) * 255 // 31
    out[..., 3] = 255
    return out


def pictures(retail):
    pic = json.load(open(os.path.join(SPEC, "pictures.json")))
    nb = len(pic["bg"])
    index = T._index((f"bg/{b}", hvq_dirty.bg(b).tobytes()) for b in range(nb))
    print("retail picture index:", len(index), flush=True)
    for mode in ("none", "q4", "q3", "mosaic", "hash3"):
        def streams():
            for b, d in enumerate(pic["bg"]):
                tw, th, nx, ny, n = d["tw"], d["th"], d["nx"], d["ny"], d["tiles"]
                g = np.frombuffer(bytes.fromhex(d["grid"]), np.uint8).reshape(n, 4, 4, 3)
                if n != nx * ny:
                    continue
                mosaic = g.reshape(ny, nx, 4, 4, 3)[::-1].transpose(0, 2, 1, 3, 4).reshape(ny * 4, nx * 4, 3)
                if mode == "mosaic":
                    im = np.repeat(np.repeat(mosaic >> 3, th // 4, 0), tw // 4, 1).astype(np.int64) * 255 // 31
                    out = np.dstack([im, np.full(im.shape[:2], 255)]).astype(np.uint8)
                else:
                    lat = generate._lattice(mosaic, nx * tw, ny * th, generate.CELL)
                    out = decode_smooth(lat, nx * tw, ny * th, generate.CELL, mode)
                # the report scans tile by tile in container order; the same rows in another order score the same
                yield f"bg/{b}", out.tobytes()
        hits = taint.scan(index, streams())
        bad = [h for h in hits if h[3] >= taint.FAIL_RUN]
        print(f"pictures {mode:7s}: {len(hits)} with coincidences, longest {max((h[3] for h in hits), default=0)} B, "
              f"{len(bad)} failing", flush=True)


def textures(retail):
    tex = json.load(open(os.path.join(SPEC, "textures.json")))
    rdirs = mainfs.read(retail)
    index = T._index(T._image_streams(rdirs))
    print("retail texture index:", len(index), flush=True)
    base_texture = generate.texture

    def variant(mode):
        def texture(key, d):
            w, h, m = d["w"], d["h"], d["mode"]
            if m == "i":
                return base_texture(key, d)
            if mode == "mosaic":
                n = int(round(len(d["grid"]) ** 0.5))
                g = np.asarray(d["grid"], np.float32).reshape(n, n, 4)
                yy, xx = np.minimum(np.arange(h) * n // h, n - 1), np.minimum(np.arange(w) * n // w, n - 1)
                rgba = g[yy][:, xx]
                rgba[..., 3] = G.unpack_alpha2(d["alpha2"], w, h) if "alpha2" in d else 255
                rgba = rgba.astype(np.uint8)
            else:
                rgba = G.from_digest(key, d)
                amp = {"none": 0, "g6": 6, "g3x8": 8, "g3x12": 12}[mode]
                if amp:
                    shape = (h, w, 1) if mode == "g6" else (h, w, 3)
                    grain = np.random.default_rng(G.h32("grain", key)).integers(-amp, amp + 1, shape)
                    rgba[..., :3] = np.clip(rgba[..., :3].astype(np.int16) + grain, 0, 255)
            if m == "ia":
                v = rgba[..., :3].astype(np.float32).mean(2).astype(np.uint8)
                rgba = np.dstack([v, v, v, rgba[..., 3]])
            elif m == "rgb":
                rgba[..., 3] = 255
            return np.ascontiguousarray(rgba)
        return texture

    for mode in ("none", "g3x8", "g3x12", "mosaic"):
        tx = variant(mode)

        def streams():
            for d, files in enumerate(rdirs):
                for f, e in enumerate(files):
                    ims = images.find(e["raw"])
                    if not ims:
                        continue
                    new = {im.key: tx(f"{d}/{f}/{im.key}", tex[f"{d}/{f}/{im.key}"]) for im in ims}
                    for im in images.find(images.rebuild(e["raw"], new)):
                        yield f"{d}/{f}/{im.key}", im.rgba.astype(np.uint8).tobytes()
        hits = taint.scan(index, streams())
        bad = [h for h in hits if h[3] >= taint.FAIL_RUN]
        modes = {}
        for h in bad:
            k = tex[h[0]]["mode"] + ("+a" if "alpha2" in tex[h[0]] else "")
            modes[k] = modes.get(k, 0) + 1
        print(f"textures {mode:7s}: {len(hits)} with coincidences, longest {max((h[3] for h in hits), default=0)} B, "
              f"{len(bad)} failing {modes}", flush=True)


if __name__ == "__main__":
    rom = open(sys.argv[1], "rb").read()
    (pictures if sys.argv[2] == "pic" else textures)(rom)
