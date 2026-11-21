"""The ffmpeg that every step calls, and what it measures.

The ffmpeg on PATH when there is one; otherwise the one in the
`imageio-ffmpeg` package from PyPI, which a sandbox with only a package
registry can install. That package has no ffprobe, so every measurement
comes from the log that ffmpeg prints. This file needs the standard library
only: speak.py and clone.py import it from their own environments.
"""

import re
import shutil
import subprocess
import sys
from functools import cache
from pathlib import Path

CLOCK = r"(\d+):(\d+):([\d.]+)"
LOUDNESS = -18  # LUFS: the level of the narrated demos in REFERENCE.md


@cache
def ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit(
            "no ffmpeg: install it (brew install ffmpeg), or `pip install imageio-ffmpeg`"
        ) from None
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str]) -> None:
    """Runs ffmpeg for its output file; a failure exits with ffmpeg's own error."""
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if done.returncode:
        sys.exit(f"{' '.join(cmd[:8])} ...\n{done.stderr[-2500:]}")


def log(*args: str) -> str:
    """The log of 1 ffmpeg run, for a measurement: an exit code of 1 is normal here."""
    return subprocess.run(
        [ffmpeg(), "-hide_banner", *args], capture_output=True, text=True, check=False
    ).stderr


def pts(text: str) -> list[float]:
    """The frame times that the `showinfo` and `metadata` filters print."""
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", text)]


def concat(path: Path) -> str:
    """1 `file` line of an ffmpeg concat list, safe for a quote in the path."""
    quoted = str(path).replace("'", "'\\''")
    return f"file '{quoted}'\n"


def seconds(path: Path) -> float:
    """The length of a media file, from the header that ffmpeg prints."""
    header = log("-i", str(path))
    found = re.search(rf"Duration: {CLOCK}", header)
    if not found:
        raise SystemExit(f"no length for {path}:\n{header[-800:]}")
    return _clock(found.groups())


def streams(video: Path) -> dict[str, list[float]]:
    """The length of each video and audio stream, measured by decoding it."""
    found: dict[str, list[float]] = {"video": [], "audio": []}
    header = log("-i", str(video))
    for index, kind in re.findall(r"Stream #0:(\d+)[^:]*: (Video|Audio)", header):
        decoded = log("-i", str(video), "-map", f"0:{index}", "-f", "null", "-")
        times = re.findall(rf"time={CLOCK}", decoded)
        found[kind.lower()].append(_clock(times[-1]) if times else 0.0)
    return found


def sound(video: Path) -> tuple[float | None, int, float]:
    """(loudness in LUFS, the count of pauses of 0.4 s or more, their total seconds)."""
    measured = log(
        *("-i", str(video), "-af", "silencedetect=noise=-35dB:d=0.4,ebur128"),
        *("-vn", "-f", "null", "-"),
    )
    pauses = [float(s) for s in re.findall(r"silence_duration: ([\d.]+)", measured)]
    loud = re.findall(r"I:\s+(-?[\d.]+) LUFS", measured)
    return (float(loud[-1]) if loud else None), len(pauses), sum(pauses)


def _clock(parts: tuple[str, str, str]) -> float:
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + float(s)
