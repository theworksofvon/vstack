import json

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
