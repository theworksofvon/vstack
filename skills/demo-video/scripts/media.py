"""The ffmpeg that every step calls, and the lengths it measures.

The ffmpeg on PATH when there is one; otherwise the one in the
`imageio-ffmpeg` package from PyPI, which a sandbox with only a package
registry can install. That package has no ffprobe, so lengths come from
ffmpeg alone.
"""

import json
import re
import shutil
import subprocess
import time
from functools import cache
from pathlib import Path


def takes(out: Path) -> list[str]:
    """The scenes of the video that have a take, in order.

    `record` and `finish` write the scene list to `scenes.json`. A frames
    folder of a scene that the list does not name is an old take, and is
    left out. Without the list, every folder with a manifest counts.
    """
    found, names = _found(out), _listed(out)
    if names is None:
        return found
    for name in sorted(set(found) - set(names)):
        print(f"{name}: not in the scene list, left out (an old take)", flush=True)
    return [n for n in names if n in found]


def untaken(out: Path) -> list[str]:
    """The scenes in `scenes.json` that have no take yet."""
    found = set(_found(out))
    return [n for n in _listed(out) or [] if n not in found]


def retire(out: Path, name: str) -> None:
    """Moves the take of scene `name` to `frames-old/`, when there is one."""
    folder = out / "frames" / name
    if not folder.exists():
        return
    old = out / "frames-old" / f"{name}-{int(time.time())}"
    old.parent.mkdir(parents=True, exist_ok=True)
    folder.rename(old)


def concat(path: Path) -> str:
    """1 `file` line of an ffmpeg concat list, safe for a quote in the path."""
    quoted = str(path).replace("'", "'\\''")
    return f"file '{quoted}'\n"


def _found(out: Path) -> list[str]:
    frames = out / "frames"
    if not frames.exists():
        return []
    return sorted(p.name for p in frames.iterdir() if (p / "manifest.json").exists())


def _listed(out: Path) -> list[str] | None:
    listed = out / "scenes.json"
    return json.loads(listed.read_text()) if listed.exists() else None


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
        )
    return imageio_ffmpeg.get_ffmpeg_exe()


def seconds(path: Path) -> float:
    """The length of a media file, from the header that ffmpeg prints."""
    log = subprocess.run(
        [ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True
    ).stderr
    found = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    if not found:
        raise SystemExit(f"no length for {path}:\n{log[-800:]}")
    h, m, s = found.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def streams(video: Path) -> dict[str, list[float]]:
    """The length of each video and audio stream, measured by decoding it."""
    log = subprocess.run(
        [ffmpeg(), "-hide_banner", "-i", str(video)], capture_output=True, text=True
    ).stderr
    found: dict[str, list[float]] = {"video": [], "audio": []}
    for index, kind in re.findall(r"Stream #0:(\d+)[^:]*: (Video|Audio)", log):
        decoded = subprocess.run(
            [ffmpeg(), "-hide_banner", "-i", str(video), "-map", f"0:{index}"]
            + ["-f", "null", "-"],
            capture_output=True,
            text=True,
        ).stderr
        times = re.findall(r"time=(\d+):(\d+):([\d.]+)", decoded)
        h, m, s = times[-1] if times else ("0", "0", "0")
        found[kind.lower()].append(int(h) * 3600 + int(m) * 60 + float(s))
    return found
