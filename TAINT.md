# Taint report

clean ROM sha1 `c7ad6118452d93bf64a9adbce496c171fc6ea0b7` (32 MB) vs the retail USA ROM.
Window 16 B, failing run >= 32 B.

| scan | retail windows indexed | clean streams with coincidences | longest shared run | failing |
|---|---|---|---|---|
| textures | 7711428 | 774 | 33 B | 1 |
| pictures | 26974664 | 158 | 31 B | 0 |
| samples | 26626720 | 45 | 25 B | 0 |
| raw image | 15234363 | 3 | 48 B | 1 |

| region | bytes | differing |
|---|---|---|
| header checksum | 8 | 8 |
| picture decoder (ours, over the HVQ2 decoder) + entry jump | 13300 | 1169 |
| MainFS | 13299840 | 11817669 |
| backgrounds | 5600144 | 5003749 |
| audio (samples, codebooks, loop states) | 8076784 | 7417512 |
| tail (free in retail) | 3222384 | 0 |

- bytes differing outside those regions: **0**
- audio bytes differing outside sample data / codebooks / loop states: **0**
- waves whose stored bytes equal retail: **0** of 870
- images whose pixels equal retail (more than 4 byte values): **0**

Kept facts (not scanned): the program (boot, code, overlays: what the matching decomp builds; contains a 1-bit 16x16 font `font0` in its data), text bank, model geometry and motion (936 FORM files without their bitmaps and palettes, 1100 MTNX motions, 17 other layout/path files incl. the 2-bit debug font 0/134), background metadata (tile counts, camera), sequences, envelopes, key maps, loop points, effect tables.

**2 failing.**

Failing streams:
- rom@0x31bfe0 at 356387: run 48 B
- 1/161/p0 at 845: run 33 B
