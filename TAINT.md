# Taint report

clean ROM sha1 `ce5db400362053818e700c7fc14bdc407fc37409` (32 MB) vs the retail USA ROM.
Window 16 B, failing run >= 32 B.

| scan | retail windows indexed | clean streams with coincidences | longest shared run | failing |
|---|---|---|---|---|
| textures | 7711428 | 771 | 42 B | 5 |
| pictures | 26974664 | 158 | 31 B | 0 |
| samples | 26626720 | 45 | 25 B | 0 |
| raw image | 15234363 | 5 | 78 B | 2 |

| region | bytes | differing |
|---|---|---|
| header checksum | 8 | 8 |
| picture decoder (ours, over the HVQ2 decoder) + entry jump | 13300 | 1169 |
| MainFS | 13299840 | 11765084 |
| backgrounds | 5600144 | 5003749 |
| audio (samples, codebooks, loop states) | 8076784 | 7417512 |
| tail (free in retail) | 3222384 | 0 |

- bytes differing outside those regions: **0**
- audio bytes differing outside sample data / codebooks / loop states: **0**
- waves whose stored bytes equal retail: **0** of 870
- images whose pixels equal retail (more than 4 byte values): **0**

Kept facts (not scanned): the program (boot, code, overlays: what the matching decomp builds; contains a 1-bit 16x16 font `font0` in its data), text bank, model geometry and motion (936 FORM files without their bitmaps and palettes, 1100 MTNX motions, 17 other layout/path files incl. the 2-bit debug font 0/134), background metadata (tile counts, camera), sequences, envelopes, key maps, loop points, effect tables.

**7 failing.**

Failing streams:
- rom@0x31bfe0 at 67125: run 78 B
- rom@0x71bfe0 at 856780: run 49 B
- 5/162/p0 at 29: run 42 B
- 5/160/p0 at 42: run 36 B
- 5/161/p0 at 0: run 36 B
- 8/14/p0 at 146: run 35 B
- 31/15/p1 at 1952: run 35 B
