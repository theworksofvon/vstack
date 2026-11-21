import json
import subprocess
from datetime import datetime

import pytest
import screen
from conftest import marks
from work import untaken


@pytest.fixture
def out(tmp_path):
    folder = tmp_path / "demo"
    folder.mkdir()
    return folder


def end(out, scene):
    return json.loads((out / "frames" / scene / "manifest.json").read_text())["end"]


def test_a_new_video_in_the_same_slug_is_extracted_again(out, film):
    marks(out, {"01": 0.0})
    screen.finish(out, film("first.mp4", 2), offset=0)
    first = end(out, "01")

    marks(out, {"01": 0.0})
    screen.finish(out, film("second.mp4", 4), offset=0)

    assert end(out, "01") > first + 1


def test_the_start_mark_begins_a_new_list(out):
    screen.mark(out, "start", None)
    screen.mark(out, "01", "old")
    screen.mark(out, "start", None)
    screen.mark(out, "02", "new")

    scenes = [
        json.loads(line)["scene"]
        for line in (out / "marks.jsonl").read_text().splitlines()
    ]
    assert scenes == ["start", "02"]


def test_a_scene_with_no_frames_loses_its_old_take(out, film):
    marks(out, {"01": 0.0, "02": 1.0})
    screen.finish(out, film("first.mp4", 2), offset=0)
    assert (out / "frames" / "02").exists()

    marks(out, {"01": 0.0, "02": 5.0})
    screen.finish(out, film("second.mp4", 2), offset=0)

    assert not (out / "frames" / "02").exists()
    assert untaken(out) == ["02"]


def test_a_creation_time_in_utc_sets_the_start(tmp_path):
    video = tmp_path / "walk.mov"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi"]
        + ["-i", "testsrc2=size=320x180:rate=30:duration=2", "-pix_fmt", "yuv420p"]
        + ["-metadata", "creation_time=2026-11-10T12:00:00.000000Z", str(video)],
        check=True,
    )
    made = datetime.fromisoformat("2026-11-10T12:00:00+00:00").timestamp()

    start = screen._start(video, [{"t": made + 0.5, "scene": "01"}], 2.0, None)

    assert start == made


INSIDE = [("a", 0.0), ("b", 0.5), ("c", 3.0), ("d", 3.2)]


def test_a_still_gap_keeps_a_short_pause():
    frames, bursts, total = screen._retime(INSIDE, 4.0, None)

    assert [t for _, t in frames] == pytest.approx([0.0, 0.5, 1.2, 1.4])
    assert bursts == [(2, pytest.approx(1.2))]
    assert total == pytest.approx(2.1)


def test_a_long_narration_grows_the_pause_up_to_the_longest():
    frames, _, total = screen._retime(INSIDE, 4.0, 10.0)

    assert [t for _, t in frames] == pytest.approx([0.0, 0.5, 3.5, 3.7])
    assert total == pytest.approx(4.5)
