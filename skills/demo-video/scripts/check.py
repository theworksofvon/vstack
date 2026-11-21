"""The checks: measure a finished video, ours or a reference from the web.

`check` fails a build that flashes or whose sound and picture differ in
length. `study` prints the same numbers for another video, so the numbers
of a good demo can become the targets of ours.
"""

import re
import subprocess
import sys
from pathlib import Path

from media import ffmpeg, streams, untaken

STEP = 40  # a brightness change of 40 in 255 between 2 frames is a visible jump
LIMIT = 3  # flashes in any 1 second: the photosensitivity limit of WCAG 2.3.1


def _stderr(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def probe(video: Path) -> dict:
    return streams(video)


def brightness(video: Path) -> list[tuple[float, float]]:
    """(time, mean brightness 0 to 255) of each frame."""
    out = subprocess.run(
        [ffmpeg(), "-v", "error", "-i", str(video), "-vf"]
        + ["scale=320:180,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-"]
        + ["-an", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stdout
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", out)]
    levels = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
    return list(zip(times, levels))


def flashes(levels: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """(the seconds that hold more than LIMIT flashes, the cuts through black)."""
    jumps = [
        (t, now - before)
        for (_, before), (t, now) in zip(levels, levels[1:])
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
    log = _stderr(
        [
            ffmpeg(),
            "-i",
            str(video),
            "-vf",
            "select='gt(scene,0.3)',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", log)]


def sound(video: Path) -> tuple[float | None, int, float]:
    """(loudness in LUFS, the count of pauses of 0.4 s or more, their total seconds)."""
    log = _stderr(
        [
            ffmpeg(),
            "-i",
            str(video),
            "-af",
            "silencedetect=noise=-35dB:d=0.4,ebur128",
            "-vn",
            "-f",
            "null",
            "-",
        ]
    )
    pauses = [float(s) for s in re.findall(r"silence_duration: ([\d.]+)", log)]
    loud = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    return (float(loud[-1]) if loud else None), len(pauses), sum(pauses)


def sheet(video: Path, length: float) -> Path:
    """30 frames, evenly spaced, in 1 image for the agent to read."""
    path = video.with_suffix(".sheet.jpg")
    every = max(length / 30, 0.5)
    subprocess.run(
        [ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf"]
        + [f"fps=1/{every:.3f},scale=384:-1,tile=6x5", "-frames:v", "1", str(path)],
        check=True,
    )
    return path


def report(video: Path) -> tuple[dict, list[str]]:
    streams = probe(video)
    length = max(streams["video"] + [0.0])
    strobes, dips = flashes(brightness(video))
    found = cuts(video)
    loud, pauses, quiet = sound(video)
    print(f"file      {video}")
    print(f"length    {length:.1f} s")
    print(f"cuts      {len(found)} hard cuts (a low estimate: slow fades do not count)")
    print(f"sound     {loud} LUFS, {pauses} pauses, {quiet:.1f} s of pause")
    print(
        f"flashes   {len(strobes)} strobes {[round(t, 1) for t in strobes]}, {len(dips)} cuts through black {[round(t, 1) for t in dips]}"
    )
    print(f"sheet     {sheet(video, length)}")
    faults = []
    if strobes:
        faults.append(
            f"more than {LIMIT} flashes in 1 second at {[round(t, 1) for t in strobes]} s"
        )
    if dips:
        faults.append(f"a cut through a black frame at {[round(t, 1) for t in dips]} s")
    if len(streams["video"]) != 1 or len(streams["audio"]) != 1:
        faults.append(
            f"{len(streams['video'])} video and {len(streams['audio'])} audio streams, not 1 and 1"
        )
    elif abs(streams["video"][0] - streams["audio"][0]) > 0.15:
        faults.append(
            f"picture is {streams['video'][0]:.2f} s and sound is {streams['audio'][0]:.2f} s"
        )
    if loud is not None and not -21 <= loud <= -15:
        faults.append(f"loudness is {loud} LUFS; the target is -18, give or take 3")
    return {"length": length}, faults


def check(out: Path) -> None:
    missing, final = untaken(out), out / "final.mp4"
    if missing:
        sys.exit(f"FAIL\n- no take of {missing}: record them, then build")
    if not final.exists():
        sys.exit("FAIL\n- no final.mp4: run build")
    _, faults = report(final)
    if faults:
        sys.exit("FAIL\n" + "\n".join(f"- {fault}" for fault in faults))
    print("PASS")


def study(source: str, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if Path(source).exists():
        video = Path(source)
    else:
        video = folder / (re.sub(r"\W+", "-", source.split("//")[-1])[-40:] + ".mp4")
        if not video.exists():
            subprocess.run(
                [
                    "yt-dlp",
                    "-q",
                    "-f",
                    "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
                ]
                + ["--merge-output-format", "mp4", "-o", str(video), source],
                check=True,
            )
    report(video)
