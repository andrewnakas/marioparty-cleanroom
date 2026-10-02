# Taint report

clean ROM sha1 `f9fa14760d8c601a1cb43aa1765a05f86e5aa468` (32 MB) vs the retail USA ROM.
Window 16 B, failing run >= 32 B.

| scan | retail windows indexed | clean streams with coincidences | longest shared run | failing |
|---|---|---|---|---|
| textures | 7711428 | 1112 | 76 B | 107 |
| pictures | 26974664 | 158 | 31 B | 0 |
| samples | 26626720 | 45 | 25 B | 0 |
| raw image | 15234363 | 6 | 78 B | 2 |

| region | bytes | differing |
|---|---|---|
| header checksum | 8 | 8 |
| picture decoder (ours, over the HVQ2 decoder) + entry jump | 13300 | 1243 |
| MainFS | 13299840 | 11868856 |
| backgrounds | 5600144 | 5231752 |
| audio (samples, codebooks, loop states) | 8076784 | 7417512 |
| tail (free in retail) | 3222384 | 0 |

- bytes differing outside those regions: **0**
- audio bytes differing outside sample data / codebooks / loop states: **0**
- waves whose stored bytes equal retail: **0** of 870
- images whose pixels equal retail (more than 4 byte values): **0**

Kept facts (not scanned): the program (boot, code, overlays: what the matching decomp builds; contains a 1-bit 16x16 font `font0` in its data), text bank, model geometry and motion (936 FORM files without their bitmaps and palettes, 1100 MTNX motions, 17 other layout/path files incl. the 2-bit debug font 0/134), background metadata (tile counts, camera), sequences, envelopes, key maps, loop points, effect tables.

**109 failing.**

Failing streams:
- rom@0x31bfe0 at 74311: run 78 B
- 21/1/p0 at 67: run 76 B
- 48/63/p0 at 0: run 68 B
- 14/4/p0 at 23: run 65 B
- 16/442/p0 at 75: run 63 B
- 21/2/p0 at 78: run 61 B
- 9/113/p0 at 622: run 58 B
- 31/11/p0 at 74: run 58 B
- 68/6/p0 at 54: run 57 B
- 10/356/p0 at 10057: run 56 B
- 11/96/p0 at 4237: run 53 B
- 16/439/p0 at 1405: run 53 B
- 31/9/p0 at 31: run 51 B
- 22/17/p0 at 21: run 50 B
- rom@0x71bfe0 at 920050: run 49 B
- 16/445/p0 at 57: run 48 B
- 16/450/p0 at 62: run 48 B
- 16/443/p0 at 67: run 47 B
- 16/432/p0 at 178: run 45 B
- 16/409/p0 at 283: run 44 B
- 16/451/p0 at 55: run 44 B
- 16/453/p0 at 9: run 44 B
- 31/10/p0 at 0: run 44 B
- 10/339/p0 at 99191: run 43 B
- 10/365/p0 at 13115: run 43 B
- 16/367/p0 at 13: run 43 B
- 16/446/p0 at 1: run 43 B
- 53/19/p0 at 3235: run 43 B
- 10/366/p0 at 1543: run 42 B
- 16/380/p0 at 69: run 42 B
- 16/436/p0 at 613: run 42 B
- 16/395/p0 at 47: run 41 B
- 16/452/p0 at 153: run 41 B
- 19/4/p6 at 39: run 41 B
- 68/7/p0 at 54303: run 41 B
- 16/410/p0 at 74: run 40 B
- 16/422/p0 at 270: run 40 B
- 10/368/p0 at 9146: run 39 B
- 16/402/p0 at 11: run 39 B
- 16/411/p0 at 95: run 39 B
- 16/420/p0 at 15: run 39 B
- 16/434/p0 at 30: run 39 B
- 16/470/p0 at 41: run 39 B
- 10/357/p0 at 10058: run 38 B
- 10/381/p0 at 230: run 38 B
- 16/109/p0 at 53: run 38 B
- 16/387/p0 at 71: run 38 B
- 16/393/p0 at 271: run 38 B
- 16/421/p0 at 90: run 38 B
- 16/433/p0 at 115: run 38 B
- 10/342/p0 at 3: run 37 B
- 10/343/p0 at 255: run 37 B
- 10/384/p0 at 145: run 37 B
- 16/254/p0 at 321: run 37 B
- 16/369/p0 at 467: run 37 B
- 16/406/p0 at 279: run 37 B
- 16/92/p0 at 561: run 36 B
- 16/331/p0 at 0: run 36 B
- 16/548/p0 at 127: run 36 B
- 10/276/p0 at 1811: run 35 B
- 16/301/p0 at 43: run 35 B
- 16/311/p0 at 201: run 35 B
- 16/379/p0 at 367: run 35 B
- 16/400/p0 at 30: run 35 B
- 16/403/p0 at 117: run 35 B
- 16/426/p0 at 226: run 35 B
- 16/441/p0 at 207: run 35 B
- 16/448/p0 at 66: run 35 B
- 16/449/p0 at 5: run 35 B
- 16/565/p0 at 131: run 35 B
- 16/573/p0 at 11: run 35 B
- 10/382/p0 at 94: run 34 B
- 10/383/p0 at 11: run 34 B
- 10/386/p0 at 71967: run 34 B
- 13/2/p0 at 2856: run 34 B
- 16/306/p0 at 33: run 34 B
- 16/386/p0 at 89: run 34 B
- 16/394/p0 at 237: run 34 B
- 16/404/p0 at 115: run 34 B
- 16/413/p0 at 371: run 34 B
- 16/415/p0 at 33: run 34 B
- 16/423/p0 at 109: run 34 B
- 16/424/p0 at 41: run 34 B
- 16/431/p0 at 235: run 34 B
- 16/440/p0 at 0: run 34 B
- 16/444/p0 at 99: run 34 B
- 16/471/p0 at 305: run 34 B
- 16/527/p0 at 70: run 34 B
- 10/241/p0 at 8883: run 33 B
- 10/392/p1 at 169: run 33 B
- 16/60/p0 at 299: run 33 B
- 16/159/p0 at 6891: run 33 B
- 16/163/p0 at 2210: run 33 B
- 16/330/p0 at 3: run 33 B
- 16/344/p0 at 1: run 33 B
- 16/368/p0 at 294: run 33 B
- 16/385/p0 at 6: run 33 B
- 16/388/p0 at 235: run 33 B
- 16/418/p0 at 117: run 33 B
- 16/435/p0 at 258: run 33 B
- 16/472/p0 at 37: run 33 B
- 10/359/p0 at 18529: run 32 B
- 10/380/p0 at 685: run 32 B
- 16/370/p0 at 266: run 32 B
- 16/376/p0 at 66: run 32 B
- 16/383/p0 at 1: run 32 B
- 16/392/p0 at 593: run 32 B
- 16/399/p0 at 297: run 32 B
- 16/417/p0 at 33: run 32 B
