"""Dev: staged ROMs to bisect boot problems.

    python -m games.marioparty.devtest <retail> <out> recomp|reloc|crq
recomp: same files, all re-compressed by our encoder, in place.  reloc: retail bytes, MainFS moved to the end.
crq: retail MainFS, every background tile a test gradient in our CRQ1 format + our decoder.
"""
import sys

from . import mainfs, romtool

retail = open(sys.argv[1], "rb").read()
dirs = mainfs.read(retail)
b = romtool.Builder(retail)
if sys.argv[3] == "recomp":
    for files in dirs:
        for e in files:
            e["comp"] = None
    b.put_mainfs(dirs)
elif sys.argv[3] == "crq":
    import numpy as np
    from . import hvqfs
    bgs = hvqfs.read(retail)
    y, x = np.mgrid[0:48, 0:64]
    for n, files in enumerate(bgs):
        for k in range(1, len(files)):
            rgba = np.dstack([x * 4, y * 5, np.full_like(x, (n * 37 + k * 11) % 256), x * 0 + 255]).astype(np.uint8)
            files[k] = hvqfs.crq(hvqfs.rgba5551(rgba))
    b.put_hvqfs(bgs)
    b.put_decoder()
else:
    b.put_mainfs(dirs, force_move=True)
open(sys.argv[2], "wb").write(b.finish())
print(sys.argv[3], b.log)
