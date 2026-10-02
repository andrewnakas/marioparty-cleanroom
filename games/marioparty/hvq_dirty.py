"""DIRTY ROOM: decode HVQ2 still images by running the game's own decoder (func_8007F54C) under Unicorn.

Only used by extract_spec (to take the coarse colour grid) and by dev contact sheets.
"""
import struct

import numpy as np
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_SP, UC_MIPS_REG_RA

BASE = 0x80000000
INIT, DECODE = 0x8007FAC0, 0x8007F54C
CODE, OUT, WORK, STOP, STACK = 0x80400000, 0x80500000, 0x80600000, 0x80700000, 0x807F0000


class Decoder:
    def __init__(self, rom):
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_BIG_ENDIAN)
        self.uc.mem_map(0, 0x800000)       # kseg0 0x80000000 = physical 0 under Unicorn
        self.uc.mem_write(0x400, bytes(rom[0x1000:0x1000 + 0x100000]))
        self.uc.mem_write(STOP - BASE, b"\0" * 16)
        # Unicorn 2 on Windows crashes natively on this code unless a global code hook is installed (slow but
        # needed once: the decoded tiles are cached by `cache()`)
        self._hook = lambda *a: None
        self.uc.hook_add(UC_HOOK_CODE, self._hook)
        self._call(INIT)

    def _call(self, addr, *args):
        for reg, v in zip((UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3), args):
            self.uc.reg_write(reg, v)
        self.uc.reg_write(UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(UC_MIPS_REG_RA, STOP)
        self.uc.emu_start(addr, STOP)

    def decode(self, data):
        """HVQ2 file -> RGBA uint8 (h, w, 4)."""
        w, h = struct.unpack_from(">HH", data, 16)
        self.uc.mem_write(CODE - BASE, bytes(data))
        self._call(DECODE, CODE, OUT, w, WORK)
        px = np.frombuffer(bytes(self.uc.mem_read(OUT - BASE, w * h * 2)), ">u2").reshape(h, w)
        out = np.empty((h, w, 4), np.uint8)
        out[..., 0] = ((px >> 11) & 31) * 255 // 31
        out[..., 1] = ((px >> 6) & 31) * 255 // 31
        out[..., 2] = ((px >> 1) & 31) * 255 // 31
        out[..., 3] = 255
        return out


CACHE = "D:/n64work/marioparty/work/hvq"


def cache_build(rom):
    """Decode every HVQ still once into the dirty work dir (resumable): bg<b>.npy (tiles, h, w, 4), fs<d>_<f>.npy."""
    import os
    import time
    from . import hvqfs, mainfs
    os.makedirs(CACHE, exist_ok=True)
    dec, t0 = Decoder(rom), time.time()
    for b, files in enumerate(hvqfs.read(rom)):
        path = f"{CACHE}/bg{b}.npy"
        if not os.path.exists(path):
            np.save(path + ".tmp.npy", np.stack([dec.decode(t) for t in files[1:]]))
            os.replace(path + ".tmp.npy", path)
            print(f"hvq bg {b} ({len(files) - 1} tiles) {time.time() - t0:.0f}s", flush=True)
    for d, files in enumerate(mainfs.read(rom)):
        for f, e in enumerate(files):
            path = f"{CACHE}/fs{d}_{f}.npy"
            if e["raw"][:4] == b"HVQ " and not os.path.exists(path):
                np.save(path, dec.decode(e["raw"]))
    print("hvq cache: done", flush=True)


def bg(b):
    return np.load(f"{CACHE}/bg{b}.npy")


def fs(d, f):
    return np.load(f"{CACHE}/fs{d}_{f}.npy")


if __name__ == "__main__":
    import sys
    cache_build(open(sys.argv[1], "rb").read())
