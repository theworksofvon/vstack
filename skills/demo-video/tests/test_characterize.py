"""Outputs of the current pipeline, held fixed while the code is cleaned up.

Each golden file in `golden/` is what the code wrote before the cleanup.
Set GOLDEN=write to write them again after a deliberate change.
"""

import json
import os
import subprocess
from pathlib import Path

import camera
import check
import edit
import pytest
import screen
from conftest import marks
from PIL import Image

GOLDEN = Path(__file__).parent / "golden"


def same(name: str, value) -> None:
    path = GOLDEN / f"{name}.json"
    if os.environ.get("GOLDEN") == "write":
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(json.dumps(value, indent=1, sort_keys=True))
    assert value == json.loads(path.read_text())


def lavfi(path: Path, *sources: str) -> Path:
    inputs = [arg for source in sources for arg in ("-f", "lavfi", "-i", source)]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-shortest"]
        + ["-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path


MANIFESTS = {
    "still": {"camera": [], "size": [1600, 900]},
    "zoom": {
        "size": [1600, 900],
        "scale": 2,
        "camera": [
            {"t": 0.5, "cx": 400, "cy": 300, "z": 1.5, "d": 0.8},
            {"t": 2.0, "cx": 800, "cy": 450, "z": 1.0, "d": 0.7},
        ],
    },
    "retarget": {
        "size": [1920, 1080],
        "scale": 3,
        "camera": [
            {"t": 0.0, "cx": 500, "cy": 500, "z": 2.0, "d": 1.0},
            {"t": 0.4, "cx": 1500, "cy": 300, "z": 1.4, "d": 0.6},
        ],
    },
}


@pytest.mark.parametrize("name", MANIFESTS)
def test_the_camera_filter_is_unchanged(name):
    m = MANIFESTS[name]
    notes = [camera.Note(**note) for note in m["camera"]]
    same(f"camera_{name}", camera.crop(notes, m["size"], m.get("scale", 2), 30))


def test_the_edit_of_a_recorded_take_is_unchanged(tmp_path):
    take = tmp_path / "frames" / "01"
    take.mkdir(parents=True)
    frames = []
    for index in range(40):
        shade = 255 if index < 10 or index > 30 else 255 - (index % 4) * 40
        Image.new("L", (400, 225), shade).save(take / f"{index:06d}.jpg")
        frames.append([f"{index:06d}.jpg", index * 0.2])
    manifest = {
        "frames": frames,
        "end": 8.2,
        "events": [{"t": 2.1, "kind": "click"}, {"t": 4.0, "kind": "key"}],
        "camera": [{"t": 2.0, "cx": 400, "cy": 300, "z": 1.4, "d": 0.8}],
        "fast": [[5.0, 7.5]],
        "caption": ["1", "A scene"],
        "card": False,
        "size": [1600, 900],
        "scale": 2,
    }
    (take / "manifest.json").write_text(json.dumps(manifest))

    edit.edit(tmp_path, "product")

    same("edit_product", json.loads((take / "cut.json").read_text()))


def test_the_screen_camera_notes_are_unchanged(tmp_path):
    video = lavfi(
        tmp_path / "walk.mp4",
        "color=white:size=640x360:rate=30:duration=5,"
        "drawbox=x=100:y=100:w=60:h=30:color=black:t=fill:enable='gte(t,1.5)',"
        "drawbox=x=400:y=200:w=50:h=40:color=red:t=fill:enable='gte(t,3.2)'",
    )
    out = tmp_path / "demo"
    out.mkdir()
    marks(out, {"01": 0.0})

    screen.finish(out, video, offset=0)

    written = json.loads((out / "frames" / "01" / "manifest.json").read_text())
    same("screen_manifest", {k: written[k] for k in ["camera", "events", "end"]})


def test_check_fails_a_video_with_no_sound(tmp_path):
    lavfi(tmp_path / "final.mp4", "testsrc2=size=640x360:rate=30:duration=2")

    with pytest.raises(SystemExit, match="1 video and 0 audio streams, not 1 and 1"):
        check.check(tmp_path)


def test_check_fails_a_video_that_is_too_loud(tmp_path):
    lavfi(
        tmp_path / "final.mp4",
        "color=gray:size=640x360:rate=30:duration=3",
        "sine=frequency=440:duration=3,volume=0.9",
    )

    with pytest.raises(SystemExit, match="the target is -18, give or take 3"):
        check.check(tmp_path)
