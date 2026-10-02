"""Clean ROM image builder: retail code + containers refilled with regenerated assets.

The image keeps the program (boot, main code, overlays: what the matching decomp builds) and every container
layout; MainFS is re-packed with our own LZSS encoder. If the new MainFS does not fit its retail span it is
appended after the retail end of data and the two lui/addiu sites that hold its address are patched.
"""
import struct

from cleanroom import rom as R
from . import hvqfs, mainfs

RETAIL_SHA1 = "1159bd56730094bfc71be30113e1cfc8bacf34f3"
FREE_START = 0x1CED490      # 0xFF padding to the end of the 32 MB image
STRINGS, STRINGS_END = 0xFCB860, 0xFE2310      # text bank (kept), between MainFS and the backgrounds
STRINGS_SITE = (0x1AE6E, 0x1AE76)               # lui/addiu holding its address (PartyPlanner64)


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
        pos, note = mainfs.ROM_OFFSET, ""
        if len(data) > span and not force_move and len(data) <= STRINGS_END - mainfs.ROM_OFFSET:
            # a little too big: move the text bank (one address site) into the free tail and use its room
            text = bytes(self.image[STRINGS:STRINGS_END])
            self.image[STRINGS:STRINGS_END] = bytes(len(text))
            tpos = self.alloc(len(text))
            self.image[tpos:tpos + len(text)] = text
            assert get_addr(self.image, *STRINGS_SITE) == STRINGS
            set_addr(self.image, *STRINGS_SITE, tpos)
            note = f", text bank moved to {tpos:#x}"
        elif len(data) > span or force_move:
            pos = self.alloc(len(data))
            for up, lo in mainfs.PATCH_SITES:
                assert get_addr(self.image, up, lo) == mainfs.ROM_OFFSET
                set_addr(self.image, up, lo, pos)
        self.image[pos:pos + len(data)] = data
        self.log.append(f"mainfs {len(data) >> 10} KB at {pos:#x} (retail span {span >> 10} KB){note}")

    def put_hvqfs(self, dirs):
        """Backgrounds: table in place; picture dirs in the retail span while they fit, the rest after the data."""
        base, span = hvqfs.ROM_OFFSET, hvqfs.ROM_END - hvqfs.ROM_OFFSET
        blobs = [hvqfs.pack_dir(files) for files in dirs]
        self.image[base:hvqfs.ROM_END] = bytes(span)
        table = bytearray(4 + 4 * (len(dirs) + 1))
        struct.pack_into(">I", table, 0, len(dirs) + 1)
        pos, moved = base + len(table), 0
        for b, blob in enumerate(blobs):
            if pos < hvqfs.ROM_END and pos + len(blob) > hvqfs.ROM_END:
                pos = self.alloc(sum(map(len, blobs[b:])))
                moved = len(blobs) - b
            struct.pack_into(">I", table, 4 + 4 * b, pos - base)
            self.image[pos:pos + len(blob)] = blob
            pos += len(blob)
        struct.pack_into(">I", table, 4 + 4 * len(dirs), pos - base)
        self.image[base:base + len(table)] = table
        self.log.append(f"backgrounds {sum(map(len, blobs)) >> 10} KB (retail span {span >> 10} KB, {moved} dirs moved)")

    def put_decoder(self):
        """Our CRQ1 decoder over the game's HVQ2 decoder entry (same signature)."""
        code = hvqfs.decoder_blob()
        self.image[hvqfs.DECODE_ROM:hvqfs.DECODE_ROM + len(code)] = code
        self.log.append(f"picture decoder {len(code)} B at {hvqfs.DECODE_ROM:#x}")

    def finish(self):
        R.finalize_crc(self.image)
        return bytes(self.image)
