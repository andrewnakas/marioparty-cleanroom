/* Our own still-image decoder that replaces the game's HVQ2 decoder (same entry point and signature:
 * decode(code, out, stride, work)).  Built for the N64 CPU with clang; position independent, no data, no calls.
 *
 * File: "CRQ1", 12 zero bytes, u16 width, u16 height (the same offsets as the HVQ2 header), 12 zero bytes, payload.
 * Payload: LZ over big-endian u16 pixels (RGBA5551).  Control byte, bits LSB first: 1 = literal pixel,
 * 0 = match (u16 distance in pixels, u16 length).  Pixels are stored XORed with the pixel above. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

void crq_decode(const u8 *code, u16 *out, u32 stride, u16 *work) {
    u32 w = (code[16] << 8) | code[17], h = (code[18] << 8) | code[19];
    const u8 *s = code + 0x20;
    u32 n = w * h, p = 0, ctl = 1, x = 0, y;
    u16 *row = out;
    while (p < n) {
        if (ctl == 1) ctl = *s++ | 0x100;
        if (ctl & 1) {
            row[x] = (s[0] << 8) | s[1];
            s += 2; p++;
            if (++x == w) { x = 0; row += stride; }
        } else {
            u32 q = p - ((s[0] << 8) | s[1]), len = (s[2] << 8) | s[3];
            u32 sx = q % w;
            const u16 *srow = out + (q / w) * stride;
            s += 4;
            for (; len && p < n; len--) {
                row[x] = srow[sx]; p++;
                if (++x == w) { x = 0; row += stride; }
                if (++sx == w) { sx = 0; srow += stride; }
            }
        }
        ctl >>= 1;
    }
    for (y = 1; y < h; y++) {
        u16 *a = out + (y - 1) * stride, *b = a + stride;
        for (x = 0; x < w; x++) b[x] ^= a[x];
    }
}
