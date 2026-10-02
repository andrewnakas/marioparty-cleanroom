"""Image containers inside MainFS files: locate, decode (dirty side) and rebuild (clean side).

Formats (PartyPlanner64 documentation + our own census):
  ImgPack   header 0x20: entry_off, extra_off, images_off, palette_off, u16 count, ..., u8 bpp at 0x19;
            entries (u32 offset, u16 w, u16 h, s16 ox, s16 oy); palette = RGBA5551 words to the end of the file.
            bpp 32 RGBA, 16 RGBA5551, 8/4 with palette = colour-indexed, 8/4 without = intensity.
  FORM      IFF chunks; BMP1 = one bitmap (format 0x128/0x228 indexed through a PAL1 chunk of RGBA32 colours,
            0x127 raw 16/32 bpp, 0x126 RGB24, 0x125 intensity+alpha, 0x124 intensity).
  RAW32     u32 4, w, h, w then RGBA32 texels (dir 10).

`find(raw)` returns a list of Img (key, w, h, mode, group, rgba) or None when the file holds no pixels we know.
`rebuild(raw, new)` writes new pixels (dict key -> RGBA uint8 array) into a copy with the same layout.
Modes: "rgba" (8-bit alpha), "rgba1" (1-bit alpha), "rgb", "ia" (intensity + alpha), "i" (intensity only).
"""
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class Img:
    key: str
    w: int
    h: int
    mode: str
    group: str        # images that share one palette
    rgba: np.ndarray  # decoded retail pixels (dirty side only)
    ncol: int = 0     # palette size for indexed images


# ---------------------------------------------------------------- pixel helpers

def rgba5551_to_rgba(words):
    w = np.asarray(words, np.uint16)
    out = np.empty(w.shape + (4,), np.uint8)
    out[..., 0] = ((w >> 11) & 31) * 255 // 31
    out[..., 1] = ((w >> 6) & 31) * 255 // 31
    out[..., 2] = ((w >> 1) & 31) * 255 // 31
    out[..., 3] = (w & 1) * 255
    return out


def rgba_to_5551(rgba):
    c = rgba.astype(np.uint16)
    r, g, b = (c[..., 0] * 31 + 127) // 255, (c[..., 1] * 31 + 127) // 255, (c[..., 2] * 31 + 127) // 255
    return ((r << 11) | (g << 6) | (b << 1) | (c[..., 3] >= 128)).astype(">u2")


def unpack_idx(data, n, bpp):
    a = np.frombuffer(data, np.uint8)
    if bpp == 8:
        return a[:n].copy()
    per = 8 // bpp
    out = np.empty(len(a) * per, np.uint8)
    for k in range(per):
        out[k::per] = (a >> (8 - bpp * (k + 1))) & ((1 << bpp) - 1)
    return out[:n]


def pack_idx(idx, bpp, nbytes):
    idx = np.asarray(idx, np.uint8).ravel()
    if bpp == 8:
        out = idx
    else:
        per = 8 // bpp
        pad = (-len(idx)) % per
        v = np.concatenate([idx, np.zeros(pad, np.uint8)]).reshape(-1, per)
        out = np.zeros(len(v), np.uint8)
        for k in range(per):
            out |= v[:, k] << (8 - bpp * (k + 1))
    b = out.tobytes()
    return b[:nbytes] + bytes(nbytes - len(b))


def quantize(images, ncol, one_bit_alpha):
    """Joint palette for a list of RGBA arrays. Returns (palette[ncol,4] uint8, [index arrays])."""
    flat = np.concatenate([im.reshape(-1, 4) for im in images])
    pal = np.zeros((max(ncol, 1), 4), np.uint8)
    if one_bit_alpha:
        solid = flat[:, 3] >= 128
        idx = np.zeros(len(flat), np.uint8)
        first = 1 if (~solid).any() and ncol > 1 else 0      # index 0 = transparent
        k = max(1, ncol - first)
        if solid.any():
            p, i = _pil_quant(flat[solid][:, :3], k, False)
            pal[first:first + len(p), :3] = p
            pal[first:first + len(p), 3] = 255
            idx[solid] = i + first
    else:
        p, idx = _pil_quant(flat, ncol, True)
        pal[:len(p)] = p
    out, pos = [], 0
    for im in images:
        n = im.shape[0] * im.shape[1]
        out.append(idx[pos:pos + n])
        pos += n
    return pal, out


def _pil_quant(pix, k, with_alpha):
    k = max(1, min(256, k))
    ch = 4 if with_alpha else 3
    width = 256
    pad = (-len(pix)) % width
    arr = np.concatenate([pix, np.repeat(pix[-1:], pad, 0)]).reshape(-1, width, ch)
    im = Image.fromarray(arr, "RGBA" if with_alpha else "RGB")
    q = im.quantize(k, method=Image.Quantize.FASTOCTREE if with_alpha else Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    p = np.array(q.getpalette("RGBA" if with_alpha else "RGB"), np.uint8).reshape(-1, ch)[:k]
    return p, np.asarray(q, np.uint8).ravel()[:len(pix)]


def _luma(rgba):
    c = rgba.astype(np.float32)
    return np.clip(c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114 + 0.5, 0, 255).astype(np.uint8)


def _grey(v, a=None):
    out = np.empty(v.shape + (4,), np.uint8)
    out[..., 0] = out[..., 1] = out[..., 2] = v
    out[..., 3] = v if a is None else a
    return out


# ---------------------------------------------------------------- ImgPack

def is_imgpack(raw):
    if len(raw) < 0x2C or struct.unpack_from(">I", raw, 0)[0] not in (0x20, 0x1B):     # two header lengths exist
        return False
    e0, u, i, p = struct.unpack_from(">4I", raw, 0)
    n = struct.unpack_from(">H", raw, 16)[0]
    return 0 < n < 4000 and e0 + 12 * n <= u <= i <= p <= len(raw) and raw[0x19] in (4, 8, 16, 32)


def _pack_entries(raw):
    n = struct.unpack_from(">H", raw, 16)[0]
    e0 = struct.unpack_from(">I", raw, 0)[0]
    return [struct.unpack_from(">IHH", raw, e0 + 12 * k) for k in range(n)]


def _pack_find(raw):
    p = struct.unpack_from(">I", raw, 12)[0]
    bpp = raw[0x19]
    haspal = p != len(raw)
    pal = rgba5551_to_rgba(np.frombuffer(raw[p:p + (len(raw) - p) // 2 * 2], ">u2")) if haspal else None
    out = []
    for k, (off, w, h) in enumerate(_pack_entries(raw)):
        if w * h == 0:
            continue
        data = raw[off:off + (w * h * bpp + 7) // 8]
        if bpp == 32:
            mode, rgba = "rgba", np.frombuffer(data, np.uint8).reshape(h, w, 4).copy()
        elif bpp == 16:
            mode, rgba = "rgba1", rgba5551_to_rgba(np.frombuffer(data, ">u2").reshape(h, w))
        elif haspal:
            idx = unpack_idx(data, w * h, bpp)
            mode, rgba = "rgba1", pal[np.minimum(idx, len(pal) - 1)].reshape(h, w, 4)
        else:
            v = unpack_idx(data, w * h, bpp).reshape(h, w)
            mode, rgba = "i", _grey(v * 17 if bpp == 4 else v)
        out.append(Img(f"p{k}", w, h, mode, "pal" if haspal else "", rgba, len(pal) if haspal else 0))
    return out


def _pack_rebuild(raw, new):
    out = bytearray(raw)
    p = struct.unpack_from(">I", raw, 12)[0]
    bpp = raw[0x19]
    haspal = p != len(raw)
    ents = [(k, off, w, h) for k, (off, w, h) in enumerate(_pack_entries(raw)) if w * h]
    if haspal:
        ncol = min((len(raw) - p) // 2, 1 << bpp)
        pal, idxs = quantize([new[f"p{k}"] for k, *_ in ents], ncol, True)
        full = np.zeros(((len(raw) - p) // 2, 4), np.uint8)
        full[:len(pal)] = pal
        out[p:p + len(full) * 2] = rgba_to_5551(full).tobytes()
    for n, (k, off, w, h) in enumerate(ents):
        size = (w * h * bpp + 7) // 8
        im = new[f"p{k}"]
        if bpp == 32:
            b = im.astype(np.uint8).tobytes()
        elif bpp == 16:
            b = rgba_to_5551(im).tobytes()
        elif haspal:
            b = pack_idx(idxs[n], bpp, size)
        else:
            v = im[..., 0]
            b = pack_idx(v >> 4 if bpp == 4 else v, bpp, size)
        out[off:off + size] = b
    return bytes(out)


# ---------------------------------------------------------------- FORM

def form_chunks(raw):
    """[(tag, body offset, size)]"""
    out, o = [], 12
    while o + 8 <= len(raw):
        n = struct.unpack_from(">I", raw, o + 4)[0]
        out.append((raw[o:o + 4], o + 8, n))
        o += 8 + n + (n & 1)
    return out


def _bmp_info(raw, o, n):
    gidx, fmt = struct.unpack_from(">HH", raw, o)
    w, h = struct.unpack_from(">HH", raw, o + 5)
    if fmt in (0x128, 0x228):
        pal = struct.unpack_from(">H", raw, o + 9)[0]
        size = struct.unpack_from(">H", raw, o + 0xF)[0]
        return dict(gidx=gidx, fmt=fmt, w=w, h=h, pal=pal, size=size, data=o + 0x11, bpp=size * 8 // max(1, w * h))
    size = struct.unpack_from(">H", raw, o + 0xB)[0]
    return dict(gidx=gidx, fmt=fmt, w=w, h=h, pal=None, size=size, data=o + 0xD, bpp=raw[o + 4])


def _form_parse(raw):
    bmps, pals = [], {}
    for n_, (tag, o, n) in enumerate(form_chunks(raw)):
        if tag == b"BMP1":
            bmps.append((n_, _bmp_info(raw, o, n)))
        elif tag == b"PAL1":
            gidx, cnt = struct.unpack_from(">HH", raw, o)
            pals.setdefault(gidx, (o + 4, cnt, (n - 4) // max(1, cnt)))
    return bmps, pals


def _form_find(raw):
    bmps, pals = _form_parse(raw)
    out = []
    for n_, b in bmps:
        w, h, d = b["w"], b["h"], b["data"]
        if w * h == 0:
            continue
        key, group, ncol = f"b{n_}", "", 0
        if b["fmt"] in (0x128, 0x228):
            if b["pal"] not in pals or pals[b["pal"]][2] != 4 or b["bpp"] not in (1, 2, 4, 8):
                raise ValueError(f"BMP1 {key}: palette {b['pal']} / bpp {b['bpp']} not handled")
            po, cnt, _ = pals[b["pal"]]
            pal = np.frombuffer(raw[po:po + cnt * 4], np.uint8).reshape(-1, 4)
            idx = unpack_idx(raw[d:d + b["size"]], w * h, b["bpp"])
            mode, rgba, group, ncol = "rgba", pal[np.minimum(idx, cnt - 1)].reshape(h, w, 4), f"pal{b['pal']}", cnt
        elif b["fmt"] == 0x127 and b["bpp"] == 32:
            mode, rgba = "rgba", np.frombuffer(raw[d:d + w * h * 4], np.uint8).reshape(h, w, 4).copy()
        elif b["fmt"] == 0x127 and b["bpp"] == 16:
            mode, rgba = "rgba1", rgba5551_to_rgba(np.frombuffer(raw[d:d + w * h * 2], ">u2").reshape(h, w))
        elif b["fmt"] == 0x126:
            rgb = np.frombuffer(raw[d:d + w * h * 3], np.uint8).reshape(h, w, 3)
            mode, rgba = "rgb", np.dstack([rgb, np.full((h, w), 255, np.uint8)])
        elif b["fmt"] == 0x125 and b["bpp"] == 8:
            v = np.frombuffer(raw[d:d + w * h], np.uint8).reshape(h, w)
            mode, rgba = "ia", _grey((v >> 4) * 17, (v & 15) * 17)
        elif b["fmt"] == 0x125 and b["bpp"] == 16:
            v = np.frombuffer(raw[d:d + w * h * 2], np.uint8).reshape(h, w, 2)
            mode, rgba = "ia", _grey(v[..., 0], v[..., 1])
        elif b["fmt"] == 0x124:
            v = np.frombuffer(raw[d:d + w * h], np.uint8).reshape(h, w)
            mode, rgba = "i", _grey(v)
        else:
            raise ValueError(f"BMP1 format {b['fmt']:#x}/{b['bpp']} not handled")
        out.append(Img(key, w, h, mode, group, rgba, ncol))
    return out


def _form_rebuild(raw, new):
    out = bytearray(raw)
    bmps, pals = _form_parse(raw)
    groups = {}
    for n_, b in bmps:
        if b["w"] * b["h"] == 0:
            continue
        key, w, h, d = f"b{n_}", b["w"], b["h"], b["data"]
        im = new[key]
        if b["fmt"] in (0x128, 0x228):
            groups.setdefault(b["pal"], []).append((key, b))
        elif b["fmt"] == 0x127 and b["bpp"] == 32:
            out[d:d + w * h * 4] = im.tobytes()
        elif b["fmt"] == 0x127:
            out[d:d + w * h * 2] = rgba_to_5551(im).tobytes()
        elif b["fmt"] == 0x126:
            out[d:d + w * h * 3] = im[..., :3].tobytes()
        elif b["fmt"] == 0x125 and b["bpp"] == 8:
            out[d:d + w * h] = ((im[..., 0] & 0xF0) | (im[..., 3] >> 4)).astype(np.uint8).tobytes()
        elif b["fmt"] == 0x125:
            out[d:d + w * h * 2] = np.dstack([im[..., 0], im[..., 3]]).astype(np.uint8).tobytes()
        else:
            out[d:d + w * h] = im[..., 0].tobytes()
    for gidx, members in groups.items():
        po, cnt, _ = pals[gidx]
        ncol = min(cnt, min(1 << b["bpp"] for _, b in members))
        pal, idxs = quantize([new[k] for k, _ in members], ncol, False)
        full = np.zeros((cnt, 4), np.uint8)
        full[:len(pal)] = pal
        out[po:po + cnt * 4] = full.tobytes()
        for (key, b), idx in zip(members, idxs):
            out[b["data"]:b["data"] + b["size"]] = pack_idx(idx, b["bpp"], b["size"])
    # palettes that no bitmap uses still hold retail colours: blank them
    used = set(groups)
    for gidx, (po, cnt, bpc) in pals.items():
        if gidx not in used:
            out[po:po + cnt * bpc] = bytes(cnt * bpc)
    return bytes(out)


# ---------------------------------------------------------------- RAW32

def is_raw32(raw):
    if len(raw) < 16:
        return False
    t, bpp, w, h = struct.unpack_from(">4I", raw, 0)
    return t == 4 and bpp == 32 and 0 < w <= 256 and 0 < h <= 256 and len(raw) == 16 + w * h * 4


# ---------------------------------------------------------------- glyph sheets (no container header of their own)
# 0/122: three sections (u32 offsets 0xc, 0x9c, 0x81c): colours, metrics, then 4-bit glyph rows (5 bytes per row).
# 0/134: a 2-bit debug font; a 2-bit image is its own 2-bit outline, so it is a kept fact as it stands.
GLYPH4 = {(0, 122): 0x81C}
KEPT_2BIT = {(0, 134)}


def glyph_levels(raw, start):
    """4-bit glyph data -> uint8 array of nibbles."""
    a = np.frombuffer(raw[start:], np.uint8)
    return np.stack([a >> 4, a & 15], 1).ravel()


def glyph_rebuild(raw, start, levels2):
    """levels2: 2-bit level per nibble (the kept outline) -> file with 4-bit glyphs at levels 0/5/10/15."""
    v = (np.asarray(levels2, np.uint8) * 5).reshape(-1, 2)
    return raw[:start] + ((v[:, 0] << 4) | v[:, 1]).astype(np.uint8).tobytes()


# ---------------------------------------------------------------- public

def kind(raw):
    if raw[:4] == b"FORM":
        return "form"
    if raw[:4] == b"HVQ ":
        return "hvq"
    if raw[:4] == b"MTNX":
        return "mtnx"
    if is_raw32(raw):
        return "raw32"
    if is_imgpack(raw):
        return "pack"
    return "other"


def find(raw):
    k = kind(raw)
    if k == "pack":
        return _pack_find(raw)
    if k == "form":
        return _form_find(raw)
    if k == "raw32":
        w, h = struct.unpack_from(">II", raw, 8)
        return [Img("r", w, h, "rgba", "", np.frombuffer(raw[16:], np.uint8).reshape(h, w, 4).copy())]
    return None


def rebuild(raw, new):
    k = kind(raw)
    if k == "pack":
        return _pack_rebuild(raw, new)
    if k == "form":
        return _form_rebuild(raw, new)
    if k == "raw32":
        return raw[:16] + new["r"].astype(np.uint8).tobytes()
    return raw
