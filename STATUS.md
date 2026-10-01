# Mario Party clean room: status

## Decisions (logged as made)
- 2026-10-01 16:03 ROM `Mario Party (USA).z64` (from `D:/Mario Party (USA).zip`) sha1 1159bd56… = the decomp's target
  (`marioparty.sha1`). Unpacked to `D:/n64work/marioparty/rom/`. Decomp: mariopartyrd/marioparty, LF clone in
  `D:/n64work/marioparty/pristine`.
- **Web route = 3: clean ROM + WASM N64 emulator** (EmulatorJS 4.2.3 + mupen64plus_next, `ports/ejs`, same as
  DK64 / Conker). Why: no PC port; the decomp is splat-based with gcc 2.7.2 (Linux binaries only) and keeps **every
  asset as a binary blob** (MainFS, HVQ backgrounds, audio), so there is nothing to compile for the web and nothing
  the decomp extracts. Retail ROM boots in headless Edge to title + Mushroom Village (dev only, 16:20).
- **Clean ROM = retail code + regenerated assets** rebuilt by our own tools (the "clean image" way from CLAUDE.md):
  code counts as kept (it is what the matching decomp builds). Containers are documented by PartyPlanner64 (MIT),
  cloned to `D:/n64work/marioparty/ref_pp64` as format reference.
- ROM-DB: the core's "Mario Party (U) [f1] (PAL)" hack slot is pointed at our ROM's MD5 (EEPROM 4 KB, rumble).
- Dev server port 8219 (8151 is used by another session).

## Works
- `games/marioparty/mainfs.py`: MainFS at 0x31C7E0 (73 dirs, 3302 files; LZSS type 1 + raw). Identity repack is
  byte-exact; own LZSS encoder (`native/mplz.c`, zig cc) round-trips all files and is ~0.5 % smaller than retail.
- `games/marioparty/images.py`: ImgPack (1161 files), FORM BMP1/PAL1 (2112 bitmaps in 936 models), RAW32.

## Next
- spec extractor (grid + 2-bit alpha), generator, clean ROM, boot test
- HVQ backgrounds (HVQ fs at 0xFE2310, 106 dirs + 55 files in MainFS dir 11): decode in the dirty room, store raw
  tiles + PartyPlanner64-style raw-tile hook
- audio (S2 x2 music banks, T3 x2 sound-effect tables), fonts / text textures, faces, voices + practice pack

## For the morning
(nothing yet)
