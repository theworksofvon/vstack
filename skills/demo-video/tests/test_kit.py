import os
import time

import kit
import pytest

GOOD = 'from kit import scene\n\n@scene("01")\ndef first(d):\n    pass\n'


@pytest.fixture
def out(tmp_path):
    (tmp_path / "scenes.py").write_text(GOOD)
    (tmp_path / "scene_02.py").write_text("this is not python\n")
    return tmp_path


def test_a_broken_scene_file_does_not_stop_the_others(out):
    scenes, broken = kit.load(out / "scenes.py")

    assert list(scenes) == ["01"]
    assert [p.name for p in broken] == ["scene_02.py"]


def test_a_full_record_stops_on_a_broken_scene_file(out):
    with pytest.raises(SystemExit, match="scene_02.py"):
        kit.record(out, None)


@pytest.fixture
def signed_in(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    (tmp_path / "login.txt").write_text("http://localhost:3000/")
    (tmp_path / "state.json").write_text("{}")
    renewals = []

    def silent(out, url):
        renewals.append(url)
        (out / "renewed").touch()
        return True

    monkeypatch.setattr(kit, "_silent", silent)
    return renewals


def test_a_recent_renewal_is_not_repeated(tmp_path, signed_in):
    kit.refresh(tmp_path)
    kit.refresh(tmp_path)

    assert len(signed_in) == 1


def test_a_saved_recording_does_not_count_as_a_renewal(tmp_path, signed_in):
    kit.refresh(tmp_path)
    old = time.time() - kit.FRESH - 1
    os.utime(tmp_path / "renewed", (old, old))
    (tmp_path / "state.json").write_text("{}")

    kit.refresh(tmp_path)

    assert len(signed_in) == 2


def test_record_stops_when_the_sign_in_ran_out(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    (tmp_path / "login.txt").write_text("http://localhost:3000/")
    monkeypatch.setattr(kit, "_silent", lambda out, url: False)

    with pytest.raises(SystemExit, match="demo login"):
        kit.refresh(tmp_path)
