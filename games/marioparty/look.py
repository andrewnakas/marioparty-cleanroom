"""Dev: boot a ROM in headless Edge (EmulatorJS dev site) and write one contact sheet.

    python -m games.marioparty.look <rom path> [script] [--cols N]

The ROM is copied to the dev site as <basename>, the dev cores get its MD5 (ROM-DB slot), then cdp_shot runs.
script is cdp_shot's ("15:shot,32:Enter:0.2,40:shot"). Starts the dev server on PORT if it is not running.
"""
import os
import shutil
import subprocess
import sys
import urllib.request

from PIL import Image

DEV = "D:/n64work/marioparty"
PORT = 8219


def serve():
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/index.html", timeout=3)
    except OSError:
        subprocess.Popen([sys.executable, "ports/wasm/serve.py", f"{DEV}/devsite", str(PORT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def main(argv):
    rom = argv[1]
    script = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else "15:shot,30:shot,32:Enter:0.2,40:shot,42:Enter:0.2,55:shot"
    cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 4
    name = os.path.basename(rom)
    site = f"{DEV}/devsite"
    if os.path.abspath(rom) != os.path.abspath(f"{site}/{name}"):
        shutil.copyfile(rom, f"{site}/{name}")
    shutil.copyfile("ports/ejs/index.html", f"{site}/index.html")
    if not os.path.isdir(f"{site}/cores_orig"):
        shutil.copytree(f"{site}/data/cores", f"{site}/cores_orig")
    subprocess.run([sys.executable, "ports/ejs/patch_core.py", f"{site}/{name}", f"{site}/cores_orig", f"{site}/data/cores"],
                   capture_output=True)
    serve()
    out = f"{DEV}/shots/{os.path.splitext(name)[0]}"
    r = subprocess.run([sys.executable, "ports/ejs/cdp_shot.py", out, "--url",
                        f"http://localhost:{PORT}/index.html?rom={name}&hb=1", "--script", script, "--gpu", "--port", "9351"],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[-1])
    shots = sorted((f for f in os.listdir(out) if f.startswith("shot_")), key=lambda f: float(f[5:-4]))
    if not shots:
        return
    w = 480
    ims = [Image.open(f"{out}/{f}").convert("RGB") for f in shots]
    ims = [i.crop((0, 0, i.width, int(i.height * 0.96))) for i in ims]
    ims = [i.resize((w, int(i.height * w / i.width))) for i in ims]
    cols = min(cols, len(ims))
    rows = (len(ims) + cols - 1) // cols
    s = Image.new("RGB", (w * cols, ims[0].height * rows))
    for k, i in enumerate(ims):
        s.paste(i, ((k % cols) * w, (k // cols) * ims[0].height))
    s.save(f"{out}/sheet.png")
    print(f"{out}/sheet.png", [f[5:-4] for f in shots])


if __name__ == "__main__":
    main(sys.argv)
