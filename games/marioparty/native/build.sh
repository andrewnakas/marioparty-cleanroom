#!/bin/sh
# host codec library + the N64 decoder blob (crq_mips.bin: raw .text placed over the game's HVQ decoder;
# crq_mips.rel: offsets of the absolute jumps (R_MIPS_26) the ROM builder rebases)
set -e
cd "$(dirname "$0")"
ZIG=~/.local/zig-x86_64-windows-0.16.0/zig.exe
OBJDUMP=~/.local/clang+llvm-23.1.2-x86_64-pc-windows-msvc/bin/llvm-objdump.exe
$ZIG cc -O2 -shared -o mplz.dll mplz.c || echo 'mplz.dll is in use: not rebuilt'
$ZIG cc -O2 -shared -o mpvadpcm.dll vadpcm.c
$ZIG cc -target mips-freestanding-eabi -mcpu=mips2 -O2 -fno-pic -mno-abicalls -ffreestanding -fno-builtin -g0 \
    -c crq_mips.c -o crq_mips.o
$OBJDUMP -r crq_mips.o | awk '/RELOCATION/ { t = ($4 == "[.text]:") } t && /R_MIPS/ { if ($2 != "R_MIPS_26" || $3 != ".text") { print "unexpected " $0; exit 1 } print $1 }' > crq_mips.rel
$ZIG objcopy -O binary -j .text crq_mips.o crq_mips.bin
rm -f crq_mips.o *.pdb *.lib
echo "built mplz.dll, crq_mips.bin $(wc -c < crq_mips.bin) bytes, $(wc -l < crq_mips.rel) jumps"
