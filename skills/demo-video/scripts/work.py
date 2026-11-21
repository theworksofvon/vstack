"""The work folder of 1 video, and where each step keeps its files.

  <slug>/scenes.py, scene_NN.py   the scenes that `record` runs
  <slug>/scenes.json              the scene list of the last record or finish
  <slug>/narration/NN.*           the narration of each scene
  <slug>/frames/NN/               the take of each scene: manifest.json, cut.json
  <slug>/frames-old/              the takes that a newer take replaced
  profiles/<host>/                the browser sign-in of 1 app, for every demo of it

This file needs the standard library only, as media.py and camera.py do.
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from camera import Note
from media import seconds

ROOT = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "vstack"
    / "demo-video"
)
ROOM = 0.8  # seconds of picture a scene keeps over its narration
SOUNDS = {".wav", ".aiff", ".mp3", ".m4a"}


@dataclass(frozen=True)
class Take:
    """1 recorded scene, as `frames/NN/manifest.json` and the edit's `cut.json` hold it.

    Times are video seconds. A take from `record` has no `source` in its file.
    """

    frames: list[list]  # [file name, time], 1 per frame
    end: float
    events: list[dict]  # {"t", "kind"}: a click or key sound
    camera: list[Note]
    fast: list[list[float]]  # [start, end] of each fast-forward span
    caption: list[str] | None  # [step, text]
    card: bool
    size: list[int]  # the page, in page pixels
    scale: float  # frame pixels per page pixel
    source: str = "record"

    @classmethod
    def load(cls, path: Path) -> "Take":
        data = json.loads(path.read_text())
        return cls(**{**data, "camera": [Note(**n) for n in data["camera"]]})

    def save(self, path: Path) -> None:
        data = asdict(self)
        if self.source == "record":
            del data["source"]
        path.write_text(json.dumps(data))


def folder(slug: str) -> Path:
    path = Path(slug).expanduser() if "/" in slug else ROOT / slug
    return path.resolve()


def profile(url: str) -> Path:
    """The browser profile of 1 app, shared by every demo of it."""
    return ROOT / "profiles" / url.split("/")[2].replace(":", "-")


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
    take = out / "frames" / name
    if not take.exists():
        return
    old = out / "frames-old" / f"{name}-{int(time.time())}"
    old.parent.mkdir(parents=True, exist_ok=True)
    take.rename(old)


def manifest(take: Path) -> Take:
    """The take as the edit left it, or as recorded when there was no edit."""
    cut = take / "cut.json"
    return Take.load(cut if cut.exists() else take / "manifest.json")


def narration(out: Path, scene: str) -> Path | None:
    """The newest sound file of the scene: an older take from another narrator loses."""
    found = [p for p in (out / "narration").glob(f"{scene}.*") if p.suffix in SOUNDS]
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def narrated(out: Path, scene: str) -> float | None:
    """The seconds of picture that hold the scene's narration, with ROOM; None without one."""
    voice = narration(out, scene)
    return seconds(voice) + ROOM if voice else None


def _found(out: Path) -> list[str]:
    frames = out / "frames"
    if not frames.exists():
        return []
    return sorted(p.name for p in frames.iterdir() if (p / "manifest.json").exists())


def _listed(out: Path) -> list[str] | None:
    listed = out / "scenes.json"
    return json.loads(listed.read_text()) if listed.exists() else None
