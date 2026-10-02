"""Background container ("HVQ fs", 0xFE2310) and our CRQ1 still-image format.

Container (big endian): u32 count (dirs + 1), u32 offset[count] (last = end); each dir: u32 count (files + 1),
u32 offset[count] relative to the dir. File 0 of a background is its 60-byte metadata (tile size, tile counts,
camera): layout, kept. The other files are the tiles, rows bottom to top.

The retail tiles are HVQ2 pictures. The clean ROM stores CRQ1 pictures instead and swaps the game's HVQ2 decoder
for ours (`native/crq_mips.c`, reached through the same entry point), so no HVQ2 bitstream is ever produced or kept.
"""
import ctypes
import os
import struct

import numpy as np

ROM_OFFSET = 0xFE2310
ROM_END = 0x15396A0           # audio (first S2 music bank) follows
DECODE_ROM = 0x8014C          # func_8007F54C (RAM 0x8007F54C): the game's HVQ2 decode entry; we put a jump here
CODE_ROM, CODE_RAM = 0x7CD60, 0x8007C160      # start of the HVQ2 decoder's code (dead once the entry jumps to ours)
CODE_ROOM = DECODE_ROM - CODE_ROM

_here = os.path.dirname(os.path.abspath(__file__))
_dll = ctypes.CDLL(os.path.join(_here, "native", "mplz.dll"))


def read(rom, base=ROM_OFFSET):
    """dirs[b] = [file bytes]."""
    u32 = lambda o: struct.unpack_from(">I", rom, o)[0]
    out = []
    for b in range(u32(base) - 1):
        bo = base + u32(base + 4 + 4 * b)
        n = u32(bo)
        offs = [u32(bo + 4 + 4 * k) for k in range(n)]
        out.append([bytes(rom[bo + offs[k]:bo + offs[k + 1]]) for k in range(n - 1)])
    return out


def pack_dir(files):
    out = bytearray(4 + 4 * (len(files) + 1))
    struct.pack_into(">I", out, 0, len(files) + 1)
    for k, f in enumerate(files):
        struct.pack_into(">I", out, 4 + 4 * k, len(out))
        out += f + bytes(-len(f) % 4)
    struct.pack_into(">I", out, 4 + 4 * len(files), len(out))
    return bytes(out)


def rgba5551(rgba):
    """RGBA uint8 (h, w, 4) -> uint16 (h, w), opaque."""
    c = (rgba[..., :3].astype(np.uint16) * 31 + 127) // 255
    return ((c[..., 0] << 11) | (c[..., 1] << 6) | (c[..., 2] << 1) | 1).astype(np.uint16)


def crq(px):
    """uint16 (h, w) pixels -> CRQ1 file."""
    h, w = px.shape
    px = np.ascontiguousarray(px, np.uint16)
    buf = ctypes.create_string_buffer(w * h * 3 + 16)
    n = _dll.crq_enc(px.ctypes.data_as(ctypes.c_void_p), w, h, buf)
    assert n > 0, "picture too large for CRQ1"
    return b"CRQ1" + bytes(12) + struct.pack(">HH", w, h) + bytes(12) + buf.raw[:n]


def crq_smooth(lattice, w, h, k):
    """RGB uint8 lattice ((h >> k) + 1, (w >> k) + 1, 3) -> CRQ2 file (the decoder interpolates)."""
    assert lattice.shape == ((h >> k) + 1, (w >> k) + 1, 3) and w % (1 << k) == 0 and h % (1 << k) == 0
    return b"CRQ2" + bytes(12) + struct.pack(">HHB", w, h, k) + bytes(11) + lattice.astype(np.uint8).tobytes()


def uncrq(data):
    w, h = struct.unpack_from(">HH", data, 16)
    out = np.zeros((h, w), np.uint16)
    _dll.crq_dec(bytes(data) + bytes(8), out.ctypes.data_as(ctypes.c_void_p), w)
    return out


def decoder_blob():
    """Our decoder's machine code, jumps rebased to its place in RAM."""
    code = bytearray(open(os.path.join(_here, "native", "crq_mips.bin"), "rb").read())
    assert len(code) <= CODE_ROOM
    for line in open(os.path.join(_here, "native", "crq_mips.rel")):
        o = int(line, 16)
        ins = struct.unpack_from(">I", code, o)[0]
        target = ((ins & 0x3FFFFFF) << 2) + CODE_RAM
        struct.pack_into(">I", code, o, (ins & 0xFC000000) | ((target >> 2) & 0x3FFFFFF))
    return bytes(code)


def entry_jump():
    """`j CODE_RAM; nop` for the game's decode entry."""
    return struct.pack(">II", 0x08000000 | ((CODE_RAM >> 2) & 0x3FFFFFF), 0)
