"""The edit: shortens still time and removes flashes. It changes times only.

Reads each scene's `manifest.json` (the recording, never changed) and writes
`cut.json` beside it, which the build step prefers.

A 0.25 s window is still when no frame in it differs from the frame before
it by more than a text caret. A still run shows for a moment, then plays at
`idle` times the speed. A window of only key presses plays at `typing` times
the speed. The rest plays at `pace`.
"""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from media import seconds

WINDOW = 0.25
ROOM = 0.8  # seconds of picture a scene keeps over its narration

# demo: real speed, only the dead time goes. product: as short as the narration allows.
MODES = {
    "demo": {"pace": (1.0, 1.0), "typing": 2.0, "idle": 4.0, "trim_fast": False},
    "product": {"pace": (1.0, 2.6), "typing": 3.0, "idle": 8.0, "trim_fast": True},
}


def narration(out: Path, scene: str) -> Path | None:
    """The newest sound file of the scene: an older take from another narrator loses."""
    found = [
        p
        for p in (out / "narration").glob(f"{scene}.*")
        if p.suffix in {".wav", ".aiff", ".mp3", ".m4a"}
    ]
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def _cached(path: Path, names: list[str], measure) -> dict:
    known = json.loads(path.read_text()) if path.exists() else {}
    if any(name not in known for name in names):
        measure(known)
        path.write_text(json.dumps(known))
    return known


def moving(folder: Path, m: dict) -> list[float]:
    """The times of the frames that differ from the frame before them."""

    def measure(known: dict) -> None:
        last = None
        for name, _ in m["frames"]:
            image = Image.open(folder / name)
            image.draft("L", (400, 225))
            small = np.asarray(image.convert("L"), dtype=np.int16)
            known[name] = bool(
                last is not None
                and last.shape == small.shape
                and int((np.abs(small - last) > 24).sum()) >= 6
            )
            last = small

    known = _cached(folder / "moving.json", [n for n, _ in m["frames"]], measure)
    return [t for name, t in m["frames"] if known[name]]


def luma(folder: Path, names: list[str]) -> dict[str, float]:
    """The mean brightness of each frame, 0 to 255."""

    def measure(known: dict) -> None:
        for name in names:
            if name not in known:
                with Image.open(folder / name) as image:
                    image.draft("L", (160, 90))
                    known[name] = float(np.asarray(image.convert("L")).mean())

    return _cached(folder / "luma.json", names, measure)


def deflash(folder: Path, m: dict, least: float = 0.6, step: float = 25) -> int:
    """Drops each dim run shorter than `least` seconds, so the frame before it holds.

    A dialog that opens and closes at high speed dims the page and brightens
    it again: several in 1 second is a strobe.
    """
    frames = m["frames"]
    level = luma(folder, [n for n, _ in frames])
    drop, start = set(), None
    for i in range(1, len(frames)):
        change = level[frames[i][0]] - level[frames[i - 1][0]]
        if change < -step and start is None:
            start = i
        elif change > step and start is not None:
            if frames[i][1] - frames[start][1] < least:
                drop.update(range(start, i))
            start = None
    m["frames"] = [f for i, f in enumerate(frames) if i not in drop]
    return len(drop)


def speeds(m: dict, idle: float, pace: float, typing: float) -> list[float]:
    keep = 0.75 * pace  # a still screen shows for 0.75 s of video before it speeds up
    count = int(m["end"] / WINDOW) + 1

    def at(t: float) -> int:
        return min(int(t / WINDOW), count - 1)

    busy, keys, others = [False] * count, [0] * count, [0] * count
    for t in m["moving"]:
        busy[at(t)] = True
    for e in m["events"]:
        (keys if e["kind"] == "key" else others)[at(e["t"])] += 1
    for k in m["camera"]:
        for i in range(at(k["t"]), at(k["t"] + k["d"]) + 1):
            others[i] += 1
    out, still = [], 0.0
    for i in range(count):
        if not others[i] and not keys[i] and not busy[i]:
            still += WINDOW
            out.append(idle if still > keep else pace)
            continue
        still = 0.0
        out.append(typing if keys[i] and not others[i] else pace)
    # A fast-forward span already shows its own speed on the screen.
    for a, b in m.get("fast") or []:
        out[at(a) : at(b) + 1] = [1.0] * (at(b) + 1 - at(a))
    return out


def warp(m: dict, factor: list[float]) -> dict:
    starts, total = [], 0.0
    for f in factor:
        starts.append(total)
        total += WINDOW / f

    def to(t: float) -> float:
        i = min(int(t / WINDOW), len(factor) - 1)
        return starts[i] + (t - i * WINDOW) / factor[i]

    return {
        **m,
        "frames": [[n, to(t)] for n, t in m["frames"]],
        "events": [{**e, "t": to(e["t"])} for e in m["events"]],
        "camera": [
            {**k, "t": to(k["t"]), "d": max(to(k["t"] + k["d"]) - to(k["t"]), 0.05)}
            for k in m["camera"]
        ],
        "end": to(m["end"]),
    }


def cut(m: dict, a: float, b: float) -> None:
    """Removes the seconds a to b: a jump cut."""

    def shift(t: float) -> float:
        return t - (b - a) if t >= b else t

    m["frames"] = [[n, shift(t)] for n, t in m["frames"] if not a <= t < b]
    m["events"] = [
        {**e, "t": shift(e["t"])} for e in m["events"] if not a <= e["t"] < b
    ]
    m["camera"] = [
        {**k, "t": shift(k["t"])} for k in m["camera"] if not a <= k["t"] < b
    ]
    m["moving"] = [shift(t) for t in m["moving"] if not a <= t < b]
    m["fast"] = [[shift(x), shift(y)] for x, y in m.get("fast") or []]
    m["end"] = shift(m["end"])


def edit(out: Path, mode: str) -> None:
    rules = MODES[mode]
    for folder in sorted(
        p for p in (out / "frames").iterdir() if (p / "manifest.json").exists()
    ):
        m = json.loads((folder / "manifest.json").read_text())
        if m.get("card"):
            (folder / "cut.json").unlink(missing_ok=True)
            continue
        m["moving"] = moving(folder, m)
        before = m["end"]
        if rules["trim_fast"]:
            for a, b in sorted(m.get("fast") or [], reverse=True):
                if b - a > 4:
                    cut(m, a + 2.2, b - 1.6)
        voice = narration(out, folder.name)
        target = seconds(voice) + ROOM if voice else 0.0
        low, high = rules["pace"]
        # A screen recording comes paced from `finish`: its pauses already fit the narration.
        pace, done = 1.0, dict(m)
        for _ in range(0 if m.get("source") == "screen" else 24):
            pace = (low + high) / 2
            done = warp(
                m, speeds(m, rules["idle"], pace, max(rules["typing"], pace * 2))
            )
            low, high = (pace, high) if done["end"] > target else (low, pace)
        done.pop("moving")
        flashes = deflash(folder, done)
        (folder / "cut.json").write_text(json.dumps(done))
        print(
            f"{folder.name}: {before:.1f} s -> {done['end']:.1f} s, action at {pace:.2f}x, "
            f"narration {target - ROOM if voice else 0:.1f} s, {flashes} flash frames dropped",
            flush=True,
        )
