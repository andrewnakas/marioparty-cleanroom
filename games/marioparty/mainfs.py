"""Mario Party (USA) MainFS: directory/file container with per-file compression.

Layout (big endian), from the PartyPlanner64 documentation:
    u32 dir_count, u32 dir_offset[dir_count]             (relative to the fs start)
    dir: u32 file_count, u32 file_offset[file_count]     (relative to the dir start)
    file: u32 decompressed_size, u32 compression_type, payload
Compression types used by MP1: 0 raw, 1 LZSS (1 KB ring), 5 RLE.

    python -m games.marioparty.mainfs <rom>      # census + identity/round-trip check
"""
import ctypes
import os
import struct
import sys

ROM_OFFSET = 0x31C7E0     # start of MainFS in the USA ROM
ROM_END = 0xFE2310        # start of the next container (HVQ backgrounds)
# lui/addiu immediates that hold the MainFS ROM address (PartyPlanner64: _mainFSOffsets MP1_USA)
PATCH_SITES = ((0x157A6, 0x157AA), (0x3C016, 0x3C01E))

_dll = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "native", "mplz.dll"))
for _n in ("mp_dec1", "mp_enc1", "mp_dec5", "mp_enc5"):
    getattr(_dll, _n).restype = ctypes.c_int


def decompress(kind, data, pos, size):
    """Return (bytes, compressed_size)."""
    if kind == 0:
        return bytes(data[pos:pos + size]), size
    out = ctypes.create_string_buffer(size + 8)
    # the decoder may read a little past the end of the stream: hand it a bounded copy
    src = bytes(data[pos:pos + size * 2 + 64])
    fn = {1: _dll.mp_dec1, 5: _dll.mp_dec5}[kind]
    used = fn(src, out, size)
    return out.raw[:size], used


def compress(kind, raw):
    if kind == 0:
        return bytes(raw)
    out = ctypes.create_string_buffer(len(raw) * 2 + 64)
    fn = {1: _dll.mp_enc1, 5: _dll.mp_enc5}[kind]
    n = fn(bytes(raw), len(raw), out)
    return out.raw[:n]


def read(rom, base=ROM_OFFSET):
    """Return dirs[d][f] = dict(kind, raw, comp)."""
    u32 = lambda o: struct.unpack_from(">I", rom, o)[0]
    dirs = []
    for d in range(u32(base)):
        doff = base + u32(base + 4 + 4 * d)
        files = []
        for f in range(u32(doff)):
            foff = doff + u32(doff + 4 + 4 * f)
            size, kind = u32(foff), u32(foff + 4)
            raw, used = decompress(kind, rom, foff + 8, size)
            files.append({"kind": kind, "raw": raw, "comp": bytes(rom[foff + 8:foff + 8 + used])})
        dirs.append(files)
    return dirs


def pack(dirs):
    """Serialise; files carry 'kind' and either 'comp' (kept as is) or only 'raw' (compressed here)."""
    out = bytearray(4 + 4 * len(dirs))
    struct.pack_into(">I", out, 0, len(dirs))
    for d, files in enumerate(dirs):
        struct.pack_into(">I", out, 4 + 4 * d, len(out))
        dstart = len(out)
        out += bytes(4 + 4 * len(files))
        struct.pack_into(">I", out, dstart, len(files))
        for f, e in enumerate(files):
            struct.pack_into(">I", out, dstart + 4 + 4 * f, len(out) - dstart)
            comp = e.get("comp")
            if comp is None:
                comp = compress(e["kind"], e["raw"])
            out += struct.pack(">II", len(e["raw"]), e["kind"]) + comp
            if len(out) & 1:
                out += b"\0"
    return bytes(out)


def main(argv):
    rom = open(argv[1], "rb").read()
    dirs = read(rom)
    nfiles = sum(len(d) for d in dirs)
    kinds = {}
    raw_total = comp_total = 0
    for d in dirs:
        for e in d:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
            raw_total += len(e["raw"])
            comp_total += len(e["comp"])
    print(f"mainfs: {len(dirs)} dirs, {nfiles} files, kinds {kinds}, raw {raw_total >> 10} KB, comp {comp_total >> 10} KB")
    same = pack(dirs)
    span = ROM_END - ROM_OFFSET
    print(f"identity repack: {len(same)} bytes of span {span}, equal={same == rom[ROM_OFFSET:ROM_OFFSET + len(same)]}")
    bad = worse = ours = 0
    for d in dirs:
        for e in d:
            if e["kind"] in (1, 5):
                c = compress(e["kind"], e["raw"])
                back, _ = decompress(e["kind"], c + bytes(64), 0, len(e["raw"]))
                bad += back != e["raw"]
                ours += len(c)
            else:
                ours += len(e["raw"])
    print(f"own encoder: round-trip failures {bad}, total {ours >> 10} KB vs retail {comp_total >> 10} KB")
    print("files per dir:", " ".join(f"{i}:{len(d)}" for i, d in enumerate(dirs)))


if __name__ == "__main__":
    main(sys.argv)
