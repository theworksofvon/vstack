import json

from work import takes, untaken


def take(out, name):
    (out / "frames" / name).mkdir(parents=True)
    (out / "frames" / name / "manifest.json").write_text("{}")


def test_an_old_take_is_reported_once(tmp_path, capsys):
    for name in ["01", "02", "05"]:
        take(tmp_path, name)
    (tmp_path / "scenes.json").write_text(json.dumps(["01", "02", "03"]))

    assert takes(tmp_path) == ["01", "02"]
    assert untaken(tmp_path) == ["03"]
    assert capsys.readouterr().out.count("05: not in the scene list") == 1
