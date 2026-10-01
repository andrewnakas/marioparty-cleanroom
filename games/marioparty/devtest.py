"""Dev: staged ROMs to bisect boot problems.

    python -m games.marioparty.devtest <retail> <out> recomp|reloc
recomp: same files, all re-compressed by our encoder, in place.  reloc: retail bytes, MainFS moved to the end.
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
else:
    b.put_mainfs(dirs, force_move=True)
open(sys.argv[2], "wb").write(b.finish())
print(sys.argv[3], b.log)
