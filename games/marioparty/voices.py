"""Voice lines: placeholder performances (Piper TTS, our own words-as-heard; no cloning of the original actors)
and the practice pack for recording real takes.

    python -m games.marioparty.voices build [name...]     # speak every line into games/marioparty/voices/
    python -m games.marioparty.voices practice            # DIRTY: practice pack in D:/n64work/marioparty/practice
                                                          # (needs voice_scan's clips; personal use, never published)

Slots are named <table>_<sound>.wave in voice_lines.json ("t3_0_336.wave" = sound 336 of the first effect table).
"_same" lists slots of the second table that hold the same line: they reuse the first one's performance.
"""
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("CLEANROOM_GAME", HERE)
from cleanroom.voice import voices as kit      # noqa: E402  (reads CLEANROOM_GAME at import)

DIRTY = "D:/n64work/marioparty/dirty/snd"
PRACTICE = "D:/n64work/marioparty/practice"
HZ = 22050


def _spec():
    return json.load(open(os.path.join(HERE, "spec", "samples.json")))


def _slot(name):
    """'t3_0_336.wave' -> spec key 't3_0/336'."""
    stem = name[:-5]
    return stem[:4] + "/" + stem[5:]


def _lines():
    d = json.load(open(os.path.join(HERE, "voice_lines.json")))
    return {k: v for k, v in d.items() if not k.startswith("_")}, d.get("_same", {})


def build(only=None):
    spec = _spec()
    kit.slots = lambda: {name: {"nframes": spec[_slot(name)]["n"], "rate": spec[_slot(name)]["rate"]} for name in _lines()[0]}
    kit.build(only)


def hook(key, d):
    """Generator hook: int16 samples for a voice slot ('snd/t3_0/336'), else None."""
    if not key.startswith("snd/t3_"):
        return None
    stem = key[4:].replace("/", "_")
    lines, same = _lines()
    stem = same.get(stem, stem)
    path = os.path.join(HERE, "voices", stem + ".wav")
    if stem + ".wave" not in lines or not os.path.exists(path):
        return None
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
        hz = w.getframerate()
    n = d["n"]
    if hz != d["rate"]:
        x = np.interp(np.arange(0, len(x), hz / d["rate"]), np.arange(len(x)), x)
    out = np.zeros(n, np.float32)
    out[:min(n, len(x))] = x[:n]
    # level: the slot's loudest kept frame
    rms = max((10 ** (f["rms"] / 20) for f in d["desc"]["frames"]), default=0.2)
    cur = np.sqrt((out ** 2).mean()) + 1e-9
    out *= min(rms * 0.8 / cur, 0.98 / (np.abs(out).max() + 1e-9))
    return (out * 32767).astype(np.int16)


def practice():
    """Standard layout: clips/, practice_<who>_call_and_response.wav (clip, 0.3 s, 80 ms 880 Hz beep, gap of
    1.5x + 1.5 s), SCRIPT.txt with '== <who>' sections."""
    spec = _spec()
    lines, _ = _lines()
    os.makedirs(os.path.join(PRACTICE, "clips"), exist_ok=True)

    def load(name):
        with wave.open(os.path.join(DIRTY, name[:-5] + ".wav")) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
            sr = w.getframerate()
        return np.interp(np.arange(0, len(x) * HZ / sr) * sr / HZ, np.arange(len(x)), x).astype(np.float32)

    def wr(path, x):
        with wave.open(path, "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(HZ)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * HZ)) / HZ)).astype(np.float32)
    by_who = {}
    for name, v in lines.items():
        by_who.setdefault(v["who"], []).append((name, v))
    script = ["Voice practice script: record in this order, 2-3 takes each, in character.",
              "Play practice_<who>_call_and_response.wav and speak after each beep.",
              "(?) = the speaker of that slot was guessed from pitch and wording: listen to the clip first.", ""]
    i = 0
    for who, items in by_who.items():
        script.append(f"== {who}")
        parts = []
        for name, v in items:
            i += 1
            x = load(name)
            wr(os.path.join(PRACTICE, "clips", f"{i:02d}_{name[:-5]}.wav"), x)
            parts += [x, np.zeros(int(0.3 * HZ), np.float32), beep, np.zeros(int((len(x) / HZ * 1.5 + 1.5) * HZ), np.float32)]
            d = spec[_slot(name)]
            script.append(f"{i:02d}  {name[:-5]:12s} max {d['n'] / d['rate']:.1f}s  \"{v['text']}\"{'  (?)' if v.get('guess') else ''}")
        wr(os.path.join(PRACTICE, f"practice_{who}_call_and_response.wav"), np.concatenate(parts))
        script.append("")
    script += ["These clips come from your own ROM: practice only, do not share or commit them."]
    open(os.path.join(PRACTICE, "SCRIPT.txt"), "w", encoding="utf8").write("\n".join(script))
    print(f"practice pack: {i} clips, tracks {sorted(by_who)} -> {PRACTICE}")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2:] or None)
    else:
        practice()
