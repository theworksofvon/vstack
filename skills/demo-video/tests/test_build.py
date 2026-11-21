import build
import check
import pytest
import screen
from conftest import marks


@pytest.fixture
def out(tmp_path, film):
    folder = tmp_path / "demo"
    folder.mkdir()
    marks(folder, {"01": 0.0, "02": 1.5})
    screen.finish(folder, film("walk.mp4", 3), offset=0)
    return folder


def test_a_preview_build_removes_the_older_final(out):
    build.build(out, None)
    assert (out / "final.mp4").exists()

    build.build(out, ["01"])

    assert (out / "preview.mp4").exists()
    assert not (out / "final.mp4").exists()


def test_check_names_the_scenes_with_no_take(out):
    build.build(out, None)
    (out / "scenes.json").write_text('["01", "02", "03"]')

    with pytest.raises(SystemExit, match=r"no take of \['03'\]"):
        check.check(out)


def test_check_fails_without_a_final_video(out):
    with pytest.raises(SystemExit, match="no final.mp4"):
        check.check(out)


def test_a_quote_in_the_work_folder_builds(tmp_path, film):
    folder = tmp_path / "o'brien"
    folder.mkdir()
    marks(folder, {"01": 0.0})
    screen.finish(folder, film("walk.mp4", 2), offset=0)

    build.build(folder, None)

    assert (folder / "final.mp4").exists()
