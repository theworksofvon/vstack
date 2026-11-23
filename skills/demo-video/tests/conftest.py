import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def film(tmp_path):
    """Films a screen recording: a moving test pattern of `length` seconds."""

    def make(name: str, length: float, pattern: str = "testsrc2") -> Path:
        video = tmp_path / name
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi"]
            + ["-i", f"{pattern}=size=640x360:rate=30:duration={length}"]
            + ["-pix_fmt", "yuv420p", str(video)],
            check=True,
        )
        return video

    return make


def marks(out: Path, scenes: dict[str, float]) -> None:
    """Writes the marks of 1 recording: `start` now, each scene `t` s after it."""
    start = time.time()
    lines = [{"t": start, "scene": "start", "caption": None}]
    lines += [{"t": start + t, "scene": s, "caption": None} for s, t in scenes.items()]
    (out / "marks.jsonl").write_text("".join(json.dumps(m) + "\n" for m in lines))
