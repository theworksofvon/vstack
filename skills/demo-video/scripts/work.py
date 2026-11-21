"""The work folder of 1 video, and where each step keeps its files.

  <slug>/scenes.py, scene_NN.py   the scenes that `record` runs
  <slug>/scenes.json              the scene list of the last record or finish
  <slug>/narration/NN.*           the narration of each scene
  <slug>/frames/NN/               the take of each scene: manifest.json, cut.json
  <slug>/frames-old/              the takes that a newer take replaced
  profiles/<host>/                the browser sign-in of 1 app, for every demo of it

This file needs the standard library only.
"""

import json
import os
import time
from pathlib import Path

ROOT = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "vstack"
    / "demo-video"
)
ROOM = 0.8  # seconds of picture a scene keeps over its narration
SOUNDS = {".wav", ".aiff", ".mp3", ".m4a"}


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


def manifest(take: Path) -> dict:
    """The take as the edit left it, or as recorded when there was no edit."""
    cut = take / "cut.json"
    return json.loads((cut if cut.exists() else take / "manifest.json").read_text())


def narration(out: Path, scene: str) -> Path | None:
    """The newest sound file of the scene: an older take from another narrator loses."""
    found = [p for p in (out / "narration").glob(f"{scene}.*") if p.suffix in SOUNDS]
    return max(found, key=lambda p: p.stat().st_mtime, default=None)


def _found(out: Path) -> list[str]:
    frames = out / "frames"
    if not frames.exists():
        return []
    return sorted(p.name for p in frames.iterdir() if (p / "manifest.json").exists())


def _listed(out: Path) -> list[str] | None:
    listed = out / "scenes.json"
    return json.loads(listed.read_text()) if listed.exists() else None
