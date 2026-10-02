# Mario Party clean room: status

## State (2026-10-01 evening)
- **Clean ROM builds, boots and plays** in headless Edge (EmulatorJS + mupen64plus-next): intro, title, Mushroom
  Village, the rules tour and its board, with sound (level tap in the dev page shows audio flowing).
- Everything the game draws or plays is regenerated: 4581 MainFS images, 105 backgrounds (4875 tiles), 55 stills,
  870 waves. The image stays 32 MB and no code address is patched.
- Not published yet: taint scan being brought to 0 failing (see "Next").

## Decisions (logged as made)
- 16:03 ROM `Mario Party (USA).z64` (from `D:/Mario Party (USA).zip`) sha1 1159bd56… = the decomp's target
  (`marioparty.sha1`). Unpacked to `D:/n64work/marioparty/rom/`. Decomp: mariopartyrd/marioparty, LF clone in
  `D:/n64work/marioparty/pristine`.
- **Web route = 3: clean ROM + WASM N64 emulator** (EmulatorJS 4.2.3 + mupen64plus_next, `ports/ejs`, same as
  DK64 / Conker). Why: no PC port; the decomp is splat-based with gcc 2.7.2 (Linux binaries only) and keeps **every
  asset as a binary blob** (MainFS, HVQ backgrounds, audio), so there is nothing to compile for the web and nothing
  the decomp extracts. 
- **Clean ROM = retail program + regenerated assets** written by our own tools (the "clean image" way from
  CLAUDE.md). Containers are documented by PartyPlanner64 (MIT), cloned to `D:/n64work/marioparty/ref_pp64`.
- **Kept as facts** (same reading of the scope as DK64/Conker): program, text bank, model geometry and motion
  (FORM without bitmaps/palettes, MTNX), layout/path tables, background metadata, sequences, envelopes, key maps,
  loop points, effect tables. Regenerated: every pixel and every sample.
- **Backgrounds**: the retail ones are HVQ2 pictures. Instead of writing an HVQ2 encoder, the game's HVQ2 decoder
  entry (`func_8007F54C`, ROM 0x8014C) is replaced by our own small decoder (`native/crq_mips.c`, built with
  `zig cc -target mips`), and pictures are stored in our own format: CRQ2 (smooth lattice, used for the kept grids,
  ~220 B per tile) or CRQ1 (LZ over 16-bit pixels, for hand-made pictures later).
- **Layout**: MainFS and the background container address directories by offsets from their tables, so tables
  stay at their retail addresses and directories fill the old spans (then the free tail). No lui/addiu patches.
- **Audio**: samples replaced in place (same byte counts), own 4-predictor VADPCM codebook written into each
  book, loop states recomputed. T3 layout: header pairs are (ctl offset, size), (tbl offset, size); PartyPlanner64's
  reader takes the wrong field for the tbl offset (cost an hour: sounds written 0x25A0 too early hung the game).
- Intensity images (masks, glyphs, effect sprites): the 2-bit outline is the picture; soft pixels get our grain.
- Fonts: the dialog glyph sheet (MainFS 0/122, 4-bit) is rebuilt from its 2-bit outline; the 2-bit debug font
  (0/134) and the 1-bit 16x16 `font0` in the program's data are their own outlines (kept as they are).
- ROM-DB: the core's "Mario Party (U) [f1] (PAL)" hack slot is pointed at our ROM's MD5 (EEPROM 4 KB, rumble).
- Dev server port 8219. Headless runs are muted (`CDP_MUTE`), nothing plays out loud.
- LZ encoder tie-break = farthest match, so a run of one byte gives a constant token (the nearest-match token
  walk is what every LZSS encoder emits and matched retail streams in the raw taint scan).

## Works
- `games/marioparty/mainfs.py` (MainFS, own LZSS, byte-exact identity repack), `images.py` (ImgPack 0x20 and 0x1b
  headers, FORM BMP1/PAL1, RAW32, glyph sheet), `hvqfs.py` + `native/crq_mips.c` (pictures), `audio.py` + 
  `native/vadpcm.c` (S2/T3 waves), `extract_spec.py` (dirty), `generate.py` (clean), `romtool.py`, `taint.py`.
- Dev: `look.py` (boot + contact sheet + audio level), `atlas.py` (retail|clean image sheets), `devtest.py`,
  `MP_OFF=` / `MP_SND=` switches in generate for bisecting (dev builds are refused by publish.sh).

## Next
1. Taint to 0 failing, then `sh tools/publish.sh push "first playable"` (creates repo + gh-pages).
2. Readability: title logo and PRESS START, HUD digits/icons/COM/rank, dice numbers, board space icons.
3. Faces: character face textures (dirs 1-6), Toad, Koopa, Bowser, Boo; HUD portraits.
4. Board backgrounds: something better than the blurred grid where it matters.
5. Voices: find the character voice waves in T3 (Whisper + listening sheets), placeholder TTS, practice pack in
   `D:/n64work/marioparty/practice/`.

## For the morning
- (will be filled once published: link, what to look at, what to record)
