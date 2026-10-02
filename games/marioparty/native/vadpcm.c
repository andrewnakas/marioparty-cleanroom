#include <stdint.h>
#define EXPORT __declspec(dllexport)

/* N64 VADPCM (order 2), a C port of cleanroom/audio/vadpcm.py (same arithmetic, same search order).
 * book: npred * 2 * 8 int16 (b0[8], b1[8] per predictor). */
#include <math.h>
static inline long long sat16(long long v) { return v < -32768 ? -32768 : v > 32767 ? 32767 : v; }

EXPORT void vadpcm_dec(const uint8_t *data, int nframes, const int16_t *book, int16_t *out) {
    long long y2 = 0, y1 = 0;
    int f, g, i, k;
    for (f = 0; f < nframes; f++, data += 9) {
        int scale = data[0] >> 4;
        const int16_t *b0 = book + (data[0] & 15) * 16, *b1 = b0 + 8;
        for (g = 0; g < 2; g++) {
            long long r[8], o[8];
            for (i = 0; i < 8; i++) {
                int byte = data[1 + g * 4 + i / 2], nb = (i & 1) ? byte & 15 : byte >> 4;
                if (nb >= 8) nb -= 16;
                r[i] = (long long)nb * (1 << scale);
            }
            for (i = 0; i < 8; i++) {
                long long acc = r[i] * 2048 + b0[i] * y2 + b1[i] * y1;
                for (k = 0; k < i; k++) acc += b1[i - 1 - k] * r[k];
                o[i] = sat16(acc >> 11);
                *out++ = (int16_t)o[i];
            }
            y2 = o[6]; y1 = o[7];
        }
    }
}

static long long enc_group(const int16_t *b0, const int16_t *b1, const int16_t *target, long long y2, long long y1,
                           int scale, int *nib, long long *out) {
    long long r[8], err = 0;
    int i, k;
    for (i = 0; i < 8; i++) {
        long long acc = b0[i] * y2 + b1[i] * y1, val;
        int n;
        for (k = 0; k < i; k++) acc += b1[i - 1 - k] * r[k];
        n = (int)nearbyint((target[i] - acc / 2048.0) / (double)(1 << scale));
        if (n < -8) n = -8;
        if (n > 7) n = 7;
        for (k = 0; k < 8; k++) {
            val = (acc + (long long)n * (1 << scale) * 2048) >> 11;
            if ((val >= -32768 && val <= 32767) || n == 0) break;
            n += n > 0 ? -1 : 1;
        }
        nib[i] = n;
        r[i] = (long long)n * (1 << scale);
        out[i] = sat16((acc + r[i] * 2048) >> 11);
        err += (out[i] - target[i]) * (out[i] - target[i]);
    }
    return err;
}

/* x: nframes*16 samples; out: nframes*9 bytes; dec: nframes*16 decoded samples */
EXPORT void vadpcm_enc(const int16_t *x, int nframes, const int16_t *book, int npred, uint8_t *out, int16_t *dec) {
    long long y2 = 0, y1 = 0;
    int f, p, s, i;
    for (f = 0; f < nframes; f++, x += 16, out += 9, dec += 16) {
        long long best = -1, bo[16] = {0};
        int bn[16] = {0}, bh = 0;
        for (p = 0; p < npred; p++)
            for (s = 0; s < 13; s++) {
                const int16_t *b0 = book + p * 16, *b1 = b0 + 8;
                int nib[16];
                long long o[16], e;
                e = enc_group(b0, b1, x, y2, y1, s, nib, o);
                e += enc_group(b0, b1, x + 8, o[6], o[7], s, nib + 8, o + 8);
                if (best < 0 || e < best) {
                    best = e; bh = (s << 4) | p;
                    for (i = 0; i < 16; i++) { bn[i] = nib[i]; bo[i] = o[i]; }
                }
            }
        out[0] = bh;
        for (i = 0; i < 16; i += 2) out[1 + i / 2] = ((bn[i] & 15) << 4) | (bn[i + 1] & 15);
        for (i = 0; i < 16; i++) dec[i] = (int16_t)bo[i];
        y2 = bo[14]; y1 = bo[15];
    }
}
