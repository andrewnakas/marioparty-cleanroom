# Mario Party — clean room web build

Play: **https://andrewnakas.github.io/marioparty-cleanroom/**

Mario Party (N64) running in the browser with **every picture and every sound regenerated**: textures,
sprites, fonts, pre-rendered board and minigame backgrounds, instrument samples, sound effects and voices.
The game program is the one the [mariopartyrd/marioparty](https://github.com/mariopartyrd/marioparty)
decompilation builds; it runs in the mupen64plus-next core of [EmulatorJS](https://github.com/EmulatorJS/EmulatorJS).

Controls: arrow keys move · `X` A · `C` B · `Z` Z · `S` R · `Q` L · `Enter` Start · `I J K L` C buttons ·
gamepads work too. Saves are kept in the browser.

## What is kept, what is generated

The decomp keeps every asset as a binary blob, so this project reads the ROM **once, in a "dirty room" step**
(`games/marioparty/extract_spec.py`), keeps only coarse facts (`games/marioparty/spec/`), and builds every
asset again from those facts (`games/marioparty/generate.py`):

| Asset (count) | Kept fact | Generated |
|---|---|---|
| Textures and sprites in MainFS (4581 images in 2129 files) | format, size, a 4×4 colour grid (16×16 from 128 px), a 2-bit alpha outline | colour from the grid plus our own noise detail; intensity masks from their 2-bit outline |
| Pre-rendered backgrounds (105 pictures, 4875 tiles) and stills (55) | tile layout and camera, one 4×4 colour grid per 64×48 tile (16×16 per still) | a smooth picture of the grid, stored in our own picture format and drawn by our own decoder, which replaces the game's HVQ2 decoder |
| Instrument and effect samples (870 waves) | length, loop points, a coarse spectral outline, one median pitch | resynthesised, encoded with our own VADPCM codebook, in place |
| Music | the note sequences (scope: melodies kept) | played by the resynthesised instruments |
| Program, text, model geometry and motion, layout tables | as built by the decomp | — |

`games/marioparty/taint.py` compares the clean ROM with the retail one: decoded textures, decoded backgrounds,
decoded samples, and the stored bytes of every retail asset against the whole clean image; shared runs of
32 bytes or more fail. It also maps every differing byte to a regenerated region. Result: [TAINT.md](TAINT.md).

No ROM is in this repository. The published site carries the clean ROM only.

## Build (Windows, Git Bash)

Needs Python 3 with numpy/Pillow/py7zr/unicorn, [Zig](https://ziglang.org) (host C compiler and the MIPS build of
the picture decoder), and your own Mario Party (USA) ROM (sha1 `1159bd56730094bfc71be30113e1cfc8bacf34f3`).

    sh games/marioparty/native/build.sh                       # codecs + the N64 picture decoder
    python -m games.marioparty.extract_spec <rom> tex         # dirty room: spec/ (already in the repo)
    python -m games.marioparty.generate <rom> clean.z64       # clean ROM
    python -m games.marioparty.taint <rom> clean.z64 TAINT.md

Formats: MainFS, ImgPack and the audio tables follow the [PartyPlanner64](https://github.com/PartyPlanner64/PartyPlanner64)
documentation; `docs/DECOMP_PLAYBOOK.md` describes the method shared with the other clean-room ports.
