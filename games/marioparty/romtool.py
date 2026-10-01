"""Clean ROM image builder: retail code + containers refilled with regenerated assets.

The image keeps the program (boot, main code, overlays: what the matching decomp builds) and every container
layout; MainFS is re-packed with our own LZSS encoder. If the new MainFS does not fit its retail span it is
appended after the retail end of data and the two lui/addiu sites that hold its address are patched.
"""
import struct

from cleanroom import rom as R
from . import mainfs

RETAIL_SHA1 = "1159bd56730094bfc71be30113e1cfc8bacf34f3"
FREE_START = 0x1CED490      # 0xFF padding to the end of the 32 MB image


def set_addr(image, upper, lower, addr):
    """Write a lui/addiu (signed low half) immediate pair."""
    lo = addr & 0xFFFF
    hi = ((addr >> 16) + (1 if lo & 0x8000 else 0)) & 0xFFFF
    struct.pack_into(">H", image, upper, hi)
    struct.pack_into(">H", image, lower, lo)


def get_addr(image, upper, lower):
    return (struct.unpack_from(">H", image, upper)[0] << 16) + struct.unpack_from(">h", image, lower)[0]


class Builder:
    def __init__(self, retail):
        self.image = bytearray(retail)
        self.free = FREE_START
        self.log = []

    def alloc(self, size, align=16):
        """Space after the retail data (grows the image past 32 MB when needed)."""
        pos = (self.free + align - 1) // align * align
        self.free = pos + size
        if self.free > len(self.image):
            grow = (self.free + 0xFFFFF) // 0x100000 * 0x100000 - len(self.image)
            self.image += b"\xff" * grow
        return pos

    def put_mainfs(self, dirs, force_move=False):
        data = mainfs.pack(dirs)
        span = mainfs.ROM_END - mainfs.ROM_OFFSET
        self.image[mainfs.ROM_OFFSET:mainfs.ROM_END] = bytes(span)
        if len(data) <= span and not force_move:
            pos = mainfs.ROM_OFFSET
        else:
            pos = self.alloc(len(data))
            for up, lo in mainfs.PATCH_SITES:
                assert get_addr(self.image, up, lo) == mainfs.ROM_OFFSET
                set_addr(self.image, up, lo, pos)
        self.image[pos:pos + len(data)] = data
        self.log.append(f"mainfs {len(data) >> 10} KB at {pos:#x} (retail span {span >> 10} KB)")

    def finish(self):
        R.finalize_crc(self.image)
        return bytes(self.image)
