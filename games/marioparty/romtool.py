"""Clean ROM image builder: retail code + containers refilled with regenerated assets.

The image keeps the program (boot, main code, overlays: what the matching decomp builds) and every container
layout; MainFS is re-packed with our own LZSS encoder and the backgrounds with our own picture format.
"""
import struct

from cleanroom import rom as R
from . import hvqfs, mainfs

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
    """Lays the regenerated containers out in the room the retail ones occupied (plus the unused tail).

    Both containers address their directories by offsets from their table, so a directory can sit anywhere after
    its table: the tables stay at their retail addresses (no code patches) and directories fill, in order, the
    MainFS span, then the background span, then the tail."""

    def __init__(self, retail):
        self.image = bytearray(retail)
        self.log = []
        for a, e in ((mainfs.ROM_OFFSET, mainfs.ROM_END), (hvqfs.ROM_OFFSET, hvqfs.ROM_END)):
            self.image[a:e] = bytes(e - a)
        ntab = 4 + 4 * struct.unpack_from(">I", retail, hvqfs.ROM_OFFSET)[0]
        self.areas = [[hvqfs.ROM_OFFSET + ntab, hvqfs.ROM_END], [FREE_START, len(retail)]]

    def alloc(self, size, align=16):
        for area in self.areas:
            pos = (area[0] + align - 1) // align * align
            if pos + size <= area[1]:
                area[0] = pos + size
                return pos
        pos = (len(self.image) + align - 1) // align * align       # last resort: grow the image
        self.image += b"\xff" * ((pos + size + 0xFFFFF) // 0x100000 * 0x100000 - len(self.image))
        self.areas.append([pos + size, len(self.image)])
        return pos

    def _place(self, base, limit, blobs):
        """Directory blobs after a table at `base`: sequentially up to `limit`, the rest via alloc()."""
        pos, offs, moved = base + 4 + 4 * len(blobs), [], 0
        for blob in blobs:
            if pos is not None and pos + len(blob) > limit:
                pos = None
            at = pos if pos is not None else self.alloc(len(blob), 2)
            moved += pos is None
            self.image[at:at + len(blob)] = blob
            offs.append(at - base)
            if pos is not None:
                pos += len(blob)
        return offs, moved

    def put_mainfs(self, dirs):
        blobs = [mainfs.pack_dir(files) for files in dirs]
        offs, moved = self._place(mainfs.ROM_OFFSET, mainfs.ROM_END, blobs)
        tab = mainfs.table(offs)
        self.image[mainfs.ROM_OFFSET:mainfs.ROM_OFFSET + len(tab)] = tab
        span = mainfs.ROM_END - mainfs.ROM_OFFSET
        self.log.append(f"mainfs {sum(map(len, blobs)) >> 10} KB (retail span {span >> 10} KB, {moved} dirs moved)")

    def put_hvqfs(self, dirs):
        """Backgrounds: table in place (count + 1 entries, the last one closes the list)."""
        base = hvqfs.ROM_OFFSET
        blobs = [hvqfs.pack_dir(files) for files in dirs]
        table = bytearray(4 + 4 * (len(dirs) + 1))
        struct.pack_into(">I", table, 0, len(dirs) + 1)
        end = 0
        for b, blob in enumerate(blobs):
            at = self.alloc(len(blob), 4)
            self.image[at:at + len(blob)] = blob
            struct.pack_into(">I", table, 4 + 4 * b, at - base)
            end = max(end, at + len(blob))
        struct.pack_into(">I", table, 4 + 4 * len(dirs), end - base)
        self.image[base:base + len(table)] = table
        self.log.append(f"backgrounds {sum(map(len, blobs)) >> 10} KB (retail {(hvqfs.ROM_END - base) >> 10} KB)")

    def put_decoder(self):
        """Our CRQ1 decoder over the game's HVQ2 decoder entry (same signature)."""
        code = hvqfs.decoder_blob()
        self.image[hvqfs.DECODE_ROM:hvqfs.DECODE_ROM + len(code)] = code
        self.log.append(f"picture decoder {len(code)} B at {hvqfs.DECODE_ROM:#x}")

    def finish(self):
        R.finalize_crc(self.image)
        return bytes(self.image)
