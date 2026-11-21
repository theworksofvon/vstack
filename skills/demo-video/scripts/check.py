"""The checks: measure a finished video, ours or a reference from the web.

`check` fails a build that flashes or whose sound and picture differ in
length. `study` prints the same numbers for another video, so the numbers
of a good demo can become the targets of ours.
"""

import re
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

from media import LOUDNESS, ffmpeg, log, pts, run, sound, streams
from work import untaken

STEP = 40  # a brightness change of 40 in 255 between 2 frames is a visible jump
LIMIT = 3  # flashes in any 1 second: the photosensitivity limit of WCAG 2.3.1
DRIFT = 0.15  # seconds that sound and picture can differ in length
LEEWAY = 3  # LU around LOUDNESS that still passes


def check(out: Path) -> None:
    missing, final = untaken(out), out / "final.mp4"
    if missing:
        sys.exit(f"FAIL\n- no take of {missing}: record them, then build")
    if not final.exists():
        sys.exit("FAIL\n- no final.mp4: run build")
    found = report(final)
    if found:
        sys.exit("FAIL\n" + "\n".join(f"- {fault}" for fault in found))
    print("PASS")


def study(source: str, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    video = Path(source)
    if not video.exists():
        video = folder / (re.sub(r"\W+", "-", source.split("//")[-1])[-40:] + ".mp4")
    if not video.exists():
        best = "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]"
        subprocess.run(
            ["yt-dlp", "-q", "-f", best, "--merge-output-format", "mp4"]
            + ["-o", str(video), source],
            check=True,
        )
    report(video)


def report(video: Path) -> list[str]:
    """Prints the measurements of `video`, and returns its faults."""
    lengths = streams(video)
    length = max(lengths["video"] + [0.0])
    strobes, dips = flashes(brightness(video))
    found = cuts(video)
    loud, pauses, quiet = sound(video)
    print(f"file      {video}")
    print(f"length    {length:.1f} s")
    print(f"cuts      {len(found)} hard cuts (a low estimate: slow fades do not count)")
    print(f"sound     {loud} LUFS, {pauses} pauses, {quiet:.1f} s of pause")
    print(
        f"flashes   {len(strobes)} strobes {_round(strobes)}, "
        f"{len(dips)} cuts through black {_round(dips)}"
    )
    print(f"sheet     {sheet(video, length)}")
    return faults(lengths, strobes, dips, loud)


def faults(
    lengths: dict[str, list[float]],
    strobes: list[float],
    dips: list[float],
    loud: float | None,
) -> list[str]:
    """The rules a finished video must meet, from its measurements."""
    found = []
    if strobes:
        found.append(f"more than {LIMIT} flashes in 1 second at {_round(strobes)} s")
    if dips:
        found.append(f"a cut through a black frame at {_round(dips)} s")
    video, audio = lengths["video"], lengths["audio"]
    if len(video) != 1 or len(audio) != 1:
        found.append(f"{len(video)} video and {len(audio)} audio streams, not 1 and 1")
    elif abs(video[0] - audio[0]) > DRIFT:
        found.append(f"picture is {video[0]:.2f} s and sound is {audio[0]:.2f} s")
    if loud is not None and abs(loud - LOUDNESS) > LEEWAY:
        found.append(
            f"loudness is {loud} LUFS; the target is {LOUDNESS}, give or take {LEEWAY}"
        )
    return found


def brightness(video: Path) -> list[tuple[float, float]]:
    """(time, mean brightness 0 to 255) of each frame."""
    levels = (
        "scale=320:180,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-"
    )
    printed = subprocess.run(
        [ffmpeg(), "-v", "error", "-i", str(video), "-vf", levels]
        + ["-an", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return list(zip(pts(printed), map(float, re.findall(r"YAVG=([\d.]+)", printed))))


def flashes(levels: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """(the seconds that hold more than LIMIT flashes, the cuts through black)."""
    jumps = [
        (t, now - before)
        for (_, before), (t, now) in pairwise(levels)
        if abs(now - before) >= STEP
    ]
    strobes = []
    for i, (t, _) in enumerate(jumps):
        inside = [j for j in jumps[i:] if j[0] - t <= 1.0]
        # A flash is 1 jump down and 1 jump up.
        if len(inside) > LIMIT * 2 and (not strobes or t - strobes[-1] > 1.0):
            strobes.append(t)
    dips = []
    for i in range(1, len(levels) - 1):
        t, level = levels[i]
        if level < 4 and levels[i - 1][1] > 80:
            after = [v for when, v in levels[i:] if when - t <= 0.5]
            if after and max(after) > 80:
                dips.append(t)
    return strobes, dips


def cuts(video: Path) -> list[float]:
    scene = "select='gt(scene,0.3)',showinfo"
    return pts(log("-i", str(video), "-vf", scene, "-an", "-f", "null", "-"))


def sheet(video: Path, length: float) -> Path:
    """30 frames, evenly spaced, in 1 image for the agent to read."""
    path = video.with_suffix(".sheet.jpg")
    every = max(length / 30, 0.5)
    run(
        [ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf"]
        + [f"fps=1/{every:.3f},scale=384:-1,tile=6x5", "-frames:v", "1", str(path)]
    )
    return path


def _round(times: list[float]) -> list[float]:
    return [round(t, 1) for t in times]
