# Mario Party clean room: status

## State (2026-10-01, late evening)
- **Published**: https://andrewnakas.github.io/marioparty-cleanroom/ (repo `andrewnakas/marioparty-cleanroom`,
  site on `gh-pages`). Checked in headless Edge against the live URL: boots, intro, title, sound flowing.
- Clean ROM = retail program + every picture and sound regenerated: 4581 MainFS images, 105 backgrounds (4875
  tiles), 55 stills, 870 waves. 32 MB, no code address patched; our picture decoder replaces the HVQ2 decoder.
- **Taint: 0 failing** (`TAINT.md`): textures, pictures, samples, raw image, plus a map of every differing byte.
- Plays: intro, title, Mushroom Village, the rules tour and its board (dice, turns, HUD) with keyboard.
- Painted / typeset so far (`games/marioparty/briefs.py`, ~830 briefs + ~230 typeset): the six players' and
  Toad's model faces and clothes, Koopa, Boo, Bowser, Shy Guy parts, HUD portraits (one drawn bust per player on
  all 578 frames), HUD digits / ranks / COM, dice faces, space icons, coins, stars, menu fonts, player names,
  board names, PRESS START, title logo lettering.
- Voices: 54 placeholder lines (Piper TTS) in `games/marioparty/voices/`; practice pack in
  `D:/n64work/marioparty/practice/` (9 call-and-response tracks + `SCRIPT.txt`).

## Decisions (logged as made)
- 16:03 ROM `Mario Party (USA).z64` (from `D:/Mario Party (USA).zip`) sha1 1159bd56… = the decomp's target.
  Decomp: mariopartyrd/marioparty, LF clone in `D:/n64work/marioparty/pristine`.
- **Web route = 3: clean ROM + WASM N64 emulator** (EmulatorJS 4.2.3 + mupen64plus_next, `ports/ejs`, same as
  DK64 / Conker). Why: no PC port; the decomp is splat-based with gcc 2.7.2 (Linux binaries only) and keeps **every
  asset as a binary blob**, so there is nothing to compile for the web and nothing the decomp extracts.
- **Clean ROM = retail program + regenerated assets** written by our own tools. Containers are documented by
  PartyPlanner64 (MIT), cloned to `D:/n64work/marioparty/ref_pp64`.
- **Kept as facts** (same reading of the scope as DK64/Conker): program, text bank, model geometry and motion
  (FORM without bitmaps/palettes, MTNX), layout/path tables, background metadata, sequences, envelopes, key maps,
  loop points, effect tables. Regenerated: every pixel and every sample.
- **Backgrounds**: instead of writing an HVQ2 encoder, the game's decode entry (`func_8007F54C`) jumps to our own
  decoder (`native/crq_mips.c`, built with `zig cc -target mips`, placed over the dead HVQ2 code). Formats: CRQ2
  (smooth lattice from the kept grid, ~220 B per tile) and CRQ1 (LZ over 16-bit pixels, for drawn pictures).
- **Layout**: both containers address directories by offsets from their tables, so the tables stay at their retail
  addresses and directories fill the old spans (then the free tail). No lui/addiu patches.
- **Audio**: samples replaced in place (same byte counts), own 4-predictor VADPCM codebook, loop states recomputed.
  T3 header pairs are (ctl offset, size), (tbl offset, size); PartyPlanner64's reader takes the wrong field for the
  tbl offset (sounds written 0x25A0 too early hung the game for an hour of bisecting). T3 rates come from the
  effect table.
- **Taint method** (same scanner as the other ports, RGBA bytes, 16-byte windows, runs >= 32 B fail):
  - 5-bit pictures have a small alphabet: a smooth ramp or a dither of the same average colour repeats 4-pixel
    windows found somewhere in 15 Mpx of retail pictures. Measured with `taint_lab.py` instead of guessing:
    backgrounds smooth 5-bit = 100 failing, hash dither = 38, **16 levels per channel = 0**; textures smooth = 138,
    grain = 5-19, **16 levels for 16-bit/palette pictures = 0**. So: no dither, 16 levels (two pictures use 8).
  - LZ encoder: farthest match and max length 65, so runs of one byte do not give the token walk every 66-step
    LZSS encoder emits. The compressed ImgPack layout tables (kept structure) are blanked in the raw scan.
- Intensity images (masks, glyphs, effect sprites): the 2-bit outline is the picture; soft pixels get our grain.
- Fonts: the dialog glyph sheet (MainFS 0/122) is rebuilt from its 2-bit outline; the 2-bit debug font (0/134)
  and the 1-bit 16x16 `font0` in the program data are their own outlines.
- Splash logos (N64, Nintendo, Hudson: 9/109-111) are left as the blurred grid on purpose: not redrawing marks.
- HUD portraits: the retail ones are 578 rendered animation frames; ours is one drawn bust per player (no
  animation). Frame ranges per player were read off a contact sheet (Peach/Wario boundary 266/267 is approximate).
- Voice speakers: announcer lines are certain; most character lines are guesses from pitch and wording (marked
  `guess` in `voice_lines.json` and `(?)` in the practice SCRIPT).
- ROM-DB: the core's "Mario Party (U) [f1] (PAL)" hack slot is pointed at our ROM's MD5 (EEPROM 4 KB, rumble).
- Dev server port 8219. Headless runs are muted (`CDP_MUTE`), nothing plays out loud.

## Tools
- Build + check + publish: `sh tools/publish.sh [push "msg"]` (refuses unless `taint: 0 failing`).
- `games/marioparty/`: `mainfs.py`, `images.py`, `hvqfs.py`, `audio.py`, `romtool.py`, `extract_spec.py` (dirty),
  `generate.py` (clean), `briefs.py` (painted/typeset pictures; `python -m games.marioparty.briefs out.png <dir>`
  previews), `voices.py`, `taint.py`, `taint_lab.py check` (5-minute texture-only taint check).
- Dev (dirty): `look.py` (boot + contact sheet + audio level), `atlas.py` (retail|clean sheets, `--zoom`),
  `voice_scan.py`, `devtest.py`, `MP_OFF=` / `MP_SND=` switches in generate (dev builds are refused by publish).

## Next
1. Title screen picture (the group picture behind the logo) and the remaining text strips in dir 10 (17, 18, 22-32).
2. Remaining dir 10 art (items, Boo, shells, coin frames, panels), dir 9 menus, minigame sprites (dirs 20-72).
3. Board backgrounds: better than the blurred grid (drawn paths / flat regions), via CRQ1 hooks.
4. Check more of the game: mode select, a full turn with a minigame, minigame instruction screens (stills).
5. Voices: confirm speakers by ear, add grunts not yet listed.

## For the morning
- Open https://andrewnakas.github.io/marioparty-cleanroom/ : Enter = Start, X = A. The first ROM download takes
  up to a minute. Tell me what looks wrong first.
- Known rough spots: board and minigame backgrounds are a blur of the kept colour grid; title picture is a blur;
  many minigame sprites are still the default rendering; HUD portraits do not animate.
- To record voices: `D:/n64work/marioparty/practice/` (SCRIPT.txt + `practice_<who>_call_and_response.wav` for
  announcer, mario, luigi, peach, yoshi, wario, dk, bowser, toad). Lines marked (?) need a listen to confirm who
  speaks. The voice kit (D:/n64work/voicekit) reads this layout.
- Decide: is one static drawn bust per player fine for the HUD, or should a few expressions be drawn?
