"""The edit: shortens still time and removes flashes. It changes times only.

Reads each scene's `manifest.json` (the recording, never changed) and writes
`cut.json` beside it, which the build step prefers.

A 0.25 s window is still when no frame in it differs from the frame before
it by more than a text caret. A still run shows for a moment, then plays at
`idle` times the speed. A window of only key presses plays at `typing` times
the speed. The rest plays at `pace`.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from work import ROOM, Take, narrated, takes

WINDOW = 0.25
MOVE_LOOK = (400, 225)  # the size each frame is compared at for motion
MOVE_DIFF = 24  # a pixel that changes by more than 24 of 255 has changed
MOVE_PIXELS = 6  # changed pixels, of MOVE_LOOK, that make a frame count as motion
DIM_STEP = 25  # a brightness drop of 25 in 255 dims the page: a dialog opens
DIM_RUN = 0.6  # seconds: a dim run shorter than this is a flash
MOVE_SHORTEST = 0.05  # seconds: the shortest camera move after a speed-up
LONG_FAST = 4  # seconds: a longer fast-forward is cut short in product mode
FAST_LEAD, FAST_TAIL = 2.2, 1.6  # seconds of a cut-short fast-forward that stay

# demo: real speed, only the dead time goes. product: as short as the narration allows.
MODES = {
    "demo": {"pace": (1.0, 1.0), "typing": 2.0, "idle": 4.0, "trim_fast": False},
    "product": {"pace": (1.0, 2.6), "typing": 3.0, "idle": 8.0, "trim_fast": True},
}


def _cached(path: Path, names: list[str], measure) -> dict:
    known = json.loads(path.read_text()) if path.exists() else {}
    if any(name not in known for name in names):
        measure(known)
        path.write_text(json.dumps(known))
    return known


def moving(folder: Path, take: Take) -> set[str]:
    """The frames that differ from the frame before them."""

    def measure(known: dict) -> None:
        last = None
        for name, _ in take.frames:
            image = Image.open(folder / name)
            image.draft("L", MOVE_LOOK)
            small = np.asarray(image.convert("L"), dtype=np.int16)
            known[name] = bool(
                last is not None
                and last.shape == small.shape
                and int((np.abs(small - last) > MOVE_DIFF).sum()) >= MOVE_PIXELS
            )
            last = small

    known = _cached(folder / "moving.json", [n for n, _ in take.frames], measure)
    return {name for name, _ in take.frames if known[name]}


def luma(folder: Path, names: list[str]) -> dict[str, float]:
    """The mean brightness of each frame, 0 to 255."""

    def measure(known: dict) -> None:
        for name in names:
            if name not in known:
                with Image.open(folder / name) as image:
                    image.draft("L", (160, 90))
                    known[name] = float(np.asarray(image.convert("L")).mean())

    return _cached(folder / "luma.json", names, measure)


def deflash(folder: Path, take: Take) -> tuple[Take, int]:
    """Drops each dim run shorter than DIM_RUN seconds, so the frame before it holds.

    A dialog that opens and closes at high speed dims the page and brightens
    it again: several in 1 second is a strobe.
    """
    frames = take.frames
    level = luma(folder, [n for n, _ in frames])
    drop, start = set(), None
    for i in range(1, len(frames)):
        change = level[frames[i][0]] - level[frames[i - 1][0]]
        if change < -DIM_STEP and start is None:
            start = i
        elif change > DIM_STEP and start is not None:
            if frames[i][1] - frames[start][1] < DIM_RUN:
                drop.update(range(start, i))
            start = None
    kept = [f for i, f in enumerate(frames) if i not in drop]
    return replace(take, frames=kept), len(drop)


def speeds(
    take: Take, motion: set[str], idle: float, pace: float, typing: float
) -> list[float]:
    keep = 0.75 * pace  # a still screen shows for 0.75 s of video before it speeds up
    count = int(take.end / WINDOW) + 1

    def at(t: float) -> int:
        return min(int(t / WINDOW), count - 1)

    busy, keys, others = [False] * count, [0] * count, [0] * count
    for name, t in take.frames:
        busy[at(t)] |= name in motion
    for e in take.events:
        (keys if e["kind"] == "key" else others)[at(e["t"])] += 1
    for note in take.camera:
        for i in range(at(note.t), at(note.t + note.d) + 1):
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
    for a, b in take.fast:
        out[at(a) : at(b) + 1] = [1.0] * (at(b) + 1 - at(a))
    return out


def warp(take: Take, factor: list[float]) -> Take:
    starts, total = [], 0.0
    for f in factor:
        starts.append(total)
        total += WINDOW / f

    def to(t: float) -> float:
        i = min(int(t / WINDOW), len(factor) - 1)
        return starts[i] + (t - i * WINDOW) / factor[i]

    return replace(
        take,
        frames=[[n, to(t)] for n, t in take.frames],
        events=[{**e, "t": to(e["t"])} for e in take.events],
        camera=[
            replace(k, t=to(k.t), d=max(to(k.t + k.d) - to(k.t), MOVE_SHORTEST))
            for k in take.camera
        ],
        end=to(take.end),
    )


def cut(take: Take, a: float, b: float) -> Take:
    """Removes the seconds a to b: a jump cut."""

    def shift(t: float) -> float:
        return t - (b - a) if t >= b else t

    return replace(
        take,
        frames=[[n, shift(t)] for n, t in take.frames if not a <= t < b],
        events=[{**e, "t": shift(e["t"])} for e in take.events if not a <= e["t"] < b],
        camera=[replace(k, t=shift(k.t)) for k in take.camera if not a <= k.t < b],
        fast=[[shift(x), shift(y)] for x, y in take.fast],
        end=shift(take.end),
    )


def fit(take: Take, motion: set[str], rules: dict, target: float) -> tuple[float, Take]:
    """The pace in the mode's range at which the take lasts `target` seconds."""
    low, high = rules["pace"]
    for _ in range(24):  # each halves the range: 24 leave it under 1e-6
        pace = (low + high) / 2
        typing = max(rules["typing"], pace * 2)
        done = warp(take, speeds(take, motion, rules["idle"], pace, typing))
        low, high = (pace, high) if done.end > target else (low, pace)
    return pace, done


def edit(out: Path, mode: str) -> None:
    rules = MODES[mode]
    for folder in (out / "frames" / name for name in takes(out)):
        take = Take.load(folder / "manifest.json")
        if take.card:
            (folder / "cut.json").unlink(missing_ok=True)
            continue
        motion = moving(folder, take)
        before = take.end
        if rules["trim_fast"]:
            for a, b in sorted(take.fast, reverse=True):
                if b - a > LONG_FAST:
                    take = cut(take, a + FAST_LEAD, b - FAST_TAIL)
        target = narrated(out, folder.name)
        # A screen recording comes paced from `finish`: its pauses already fit the narration.
        pace, done = 1.0, take
        if take.source != "screen":
            pace, done = fit(take, motion, rules, target or 0.0)
        done, flashes = deflash(folder, done)
        done.save(folder / "cut.json")
        print(
            f"{folder.name}: {before:.1f} s -> {done.end:.1f} s, action at {pace:.2f}x, "
            f"narration {target - ROOM if target else 0:.1f} s, {flashes} flash frames dropped",
            flush=True,
        )
