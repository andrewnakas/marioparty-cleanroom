"""DIRTY ROOM dev tool: export the sound-effect waves as WAV into the dirty work dir and list voice candidates.

    python -m games.marioparty.voice_scan <retail rom> [whisper]

Writes D:/n64work/marioparty/dirty/snd/<group>_<n>.wav and voice_scan.tsv next to them:
name, seconds, rate, median f0, voiced share, harmonicity, what Whisper hears (with "whisper").
The clips and the table stay in the dirty work dir (never the repo); they are for deciding which slots are
character voices and for the practice pack.
"""
import json
import os
import sys
import wave

import numpy as np

from . import audio

OUT = "D:/n64work/marioparty/dirty/snd"
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec", "samples.json")


def main(argv):
    rom = open(argv[1], "rb").read()
    os.makedirs(OUT, exist_ok=True)
    spec = json.load(open(SPEC))
    model = None
    if "whisper" in argv:
        from faster_whisper import WhisperModel
        import librosa
        model = WhisperModel("base.en", device="cpu", compute_type="int8")
    rows = []
    for w in audio.waves(rom):
        if not w["name"].startswith("t3"):
            continue
        pcm = audio.decode(rom, w)
        rate = w["rate"]
        name = w["name"].replace("/", "_")
        with wave.open(f"{OUT}/{name}.wav", "wb") as f:
            f.setnchannels(1), f.setsampwidth(2), f.setframerate(rate)
            f.writeframes(pcm.astype("<i2").tobytes())
        d = spec[w["name"]]
        fr = d["desc"]["frames"]
        voiced = sum(1 for x in fr if x["f0"] > 20 and x["h"] > 0.3) / max(1, len(fr))
        harm = float(np.mean([x["h"] for x in fr])) if fr else 0
        heard = ""
        secs = len(pcm) / rate
        if model is not None and 0.2 <= secs <= 6 and not w["loop"]:
            x16 = librosa.resample(pcm.astype(np.float32) / 32768, orig_sr=rate, target_sr=16000)
            segs, _ = model.transcribe(np.concatenate([np.zeros(1600, np.float32), x16, np.zeros(8000, np.float32)]),
                                       language="en", beam_size=5)
            heard = " ".join(s.text for s in segs).strip()
        rows.append((w["name"], secs, rate, d.get("f0", 0), voiced, harm, 1 if w["loop"] else 0, heard))
    with open(f"{OUT}/voice_scan.tsv", "w", encoding="utf-8") as f:
        for r in rows:
            f.write("%s\t%.2f\t%d\t%.0f\t%.2f\t%.2f\t%d\t%s\n" % r)
    print(f"voice_scan: {len(rows)} clips -> {OUT}; {sum(1 for r in rows if r[7])} with words heard")


if __name__ == "__main__":
    main(sys.argv)
