/* Mario Party (N64) MainFS codecs: type 1 (LZSS, 1 KB ring starting at 0x3BE) and type 5 (RLE). */
#include <stdint.h>
#include <string.h>
#define WIN 1024
#define WSTART 0x3BE
#define EXPORT __declspec(dllexport)

/* returns compressed bytes consumed */
EXPORT int mp_dec1(const uint8_t *src, uint8_t *dst, int dlen) {
    uint8_t win[WIN];
    int sp = 0, dp = 0, wp = WSTART;
    unsigned code = 0;
    memset(win, 0, WIN);
    while (dp < dlen) {
        if (!(code & 0x100)) code = src[sp++] | 0xff00;
        if (code & 1) {
            uint8_t b = src[sp++];
            dst[dp++] = b; win[wp] = b; wp = (wp + 1) & (WIN - 1);
        } else {
            int b1 = src[sp], b2 = src[sp + 1], off, n, i;
            sp += 2;
            off = ((b2 & 0xc0) << 2) | b1;
            n = (b2 & 0x3f) + 3;
            for (i = 0; i < n && dp < dlen; i++) {
                uint8_t v = win[(off + i) & (WIN - 1)];
                win[wp] = v; wp = (wp + 1) & (WIN - 1);
                dst[dp++] = v;
            }
        }
        code >>= 1;
    }
    return sp;
}

/* greedy encoder with one-step lazy matching; returns compressed size. dst must hold slen*9/8+16. */
static int best_match(const uint8_t *src, int pos, int slen, int *moff) {
    int best = 0, maxlen = slen - pos, d, lo;
    if (maxlen > 66) maxlen = 66;
    if (maxlen < 3) return 0;
    /* a match may start up to 1023 bytes back (distance d); ring position = (WSTART + pos - d) */
    lo = pos < 1023 ? pos : 1023;
    for (d = 1; d <= lo; d++) {
        const uint8_t *p = src + pos - d;
        int n = 0;
        if (p[0] != src[pos]) continue;
        while (n < maxlen && p[n] == src[pos + n]) n++;   /* overlap is fine: decoder copies byte by byte */
        if (n > best) { best = n; *moff = d; if (n == maxlen) break; }
    }
    /* never reference the ring before the start of the file: the game's decoder does not clear it */
    return best >= 3 ? best : 0;
}

EXPORT int mp_enc1(const uint8_t *src, int slen, uint8_t *dst) {
    int sp = 0, dp = 0, codepos = -1, bit = 8;
    while (sp < slen) {
        int off = 0, n, off2 = 0, n2;
        if (bit == 8) { codepos = dp++; dst[codepos] = 0; bit = 0; }
        n = best_match(src, sp, slen, &off);
        if (n >= 3 && sp + 1 < slen) {
            n2 = best_match(src, sp + 1, slen, &off2);
            if (n2 > n + 1) n = 0;
        }
        if (n >= 3) {
            int ring = (WSTART + sp - off) & (WIN - 1);
            dst[dp++] = ring & 0xff;
            dst[dp++] = ((ring >> 2) & 0xc0) | (n - 3);
            sp += n;
        } else {
            dst[codepos] |= 1 << bit;
            dst[dp++] = src[sp++];
        }
        bit++;
    }
    return dp;
}

EXPORT int mp_dec5(const uint8_t *src, uint8_t *dst, int dlen) {
    int sp = 0, dp = 0;
    while (dp < dlen) {
        int c = src[sp++], n = c & 0x7f, i;
        if (c & 0x80) { for (i = 0; i < n && dp < dlen; i++) dst[dp++] = src[sp++]; }
        else { uint8_t b = src[sp++]; for (i = 0; i < n && dp < dlen; i++) dst[dp++] = b; }
    }
    return sp;
}

EXPORT int mp_enc5(const uint8_t *src, int slen, uint8_t *dst) {
    int sp = 0, dp = 0;
    while (sp < slen) {
        int run = 1;
        while (sp + run < slen && run < 127 && src[sp + run] == src[sp]) run++;
        if (run >= 2) { dst[dp++] = run; dst[dp++] = src[sp]; sp += run; }
        else {
            int n = 0, hdr = dp++;
            while (sp < slen && n < 127 && !(sp + 1 < slen && src[sp + 1] == src[sp])) dst[dp++] = src[sp++], n++;
            dst[hdr] = 0x80 | n;
        }
    }
    return dp;
}

/* CRQ1 payload encoder (see crq_mips.c): px = w*h big-endian-agnostic u16 values; returns bytes written.
 * dst must hold n*2 + n/4 + 16. */
#define CH 15
EXPORT int crq_enc(const uint16_t *px, int w, int h, uint8_t *dst) {
    static int head[1 << CH], prev[1 << 16];
    static uint16_t r[1 << 16];
    int n = w * h, i, sp = 0, dp = 0, codepos = -1, bit = 8;
    if (n > (1 << 16)) return -1;
    for (i = 0; i < n; i++) r[i] = i >= w ? px[i] ^ px[i - w] : px[i];
    memset(head, 0xff, sizeof head);
    while (sp < n) {
        int best = 0, boff = 0, tries = 64, c;
        unsigned hsh = 0;
        if (bit == 8) { codepos = dp++; dst[codepos] = 0; bit = 0; }
        if (sp + 2 < n) {
            hsh = ((r[sp] * 2654435761u) ^ (r[sp + 1] * 40503u) ^ (r[sp + 2] * 97u)) >> 7 & ((1 << CH) - 1);
            for (c = head[hsh]; c >= 0 && tries--; c = prev[c]) {
                int m = 0;
                while (sp + m < n && r[c + m] == r[sp + m]) m++;
                if (m > best) { best = m; boff = sp - c; }
            }
        }
        if (best >= 3) {
            dst[dp++] = boff >> 8; dst[dp++] = boff; dst[dp++] = best >> 8; dst[dp++] = best;
        } else {
            best = 1;
            dst[codepos] |= 1 << bit;
            dst[dp++] = r[sp] >> 8; dst[dp++] = r[sp];
        }
        for (i = 0; i < best; i++, sp++) {
            if (sp + 2 < n) {
                unsigned k = ((r[sp] * 2654435761u) ^ (r[sp + 1] * 40503u) ^ (r[sp + 2] * 97u)) >> 7 & ((1 << CH) - 1);
                prev[sp] = head[k]; head[k] = sp;
            }
        }
        bit++;
    }
    return dp;
}

/* reference decoder = crq_mips.c compiled for the host (round-trip tests) */
#define crq_decode crq_host_decode_impl
#include "crq_mips.c"
#undef crq_decode
EXPORT void crq_dec(const uint8_t *code, uint16_t *out, unsigned stride) { crq_host_decode_impl(code, out, stride, 0); }
