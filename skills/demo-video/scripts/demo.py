#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright", "numpy", "soundfile", "pillow", "imageio-ffmpeg"]
# ///
"""Record a narrated demo of a live web app.

  demo.py init <slug>                 make the work folder with a scenes.py to fill in
  demo.py login <slug> <url>          sign in 1 time in a window; the session is saved
  demo.py voices ["a sentence"]       1 sample file per voice, to listen and pick
  demo.py narrate <slug> [--voice V] [--speed N]   narration/NN.txt -> narration/NN.wav
  demo.py clone <recording or "record"> ["words"]   the user's voice, 1 time; then --voice me
  demo.py record <slug> [scenes]      run scenes.py in a browser, save the frames
  demo.py edit <slug> --mode M        cut dead time: demo (real speed) or product (short)
  demo.py build <slug> [scenes]       frames + narration -> final.mp4 (preview.mp4 for a subset)
  demo.py check <slug>                fail on flashes or on sound and picture that differ
  demo.py study <url or file>         measure another video: length, cuts, pauses, loudness
  demo.py selftest                    run the full flow on a built-in page
  demo.py doctor [url]                what this machine can do, and 1 fix per gap
  demo.py package [file.zip]          the skill as a zip for claude.ai > Skills > Upload

The screen path, when the user's own recorder films the walk-through:
  demo.py mark <slug> <NN or start> ["caption"]   stamp the start of a scene, now
  demo.py finish <slug> <recording> [--offset S]  recording -> frames/NN, then edit, build, check
  demo.py overlay                     the drawn cursor as 1 script for a browser tool's JavaScript

<slug> is a folder name under ${XDG_CACHE_HOME:-~/.cache}/vstack/demo-video/,
or a path. [scenes] is a comma list such as 01,02.
"""

import argparse
import os
import shutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path

from work import ROOT, folder

HERE = Path(__file__).parent

TEMPLATE = '''"""The scenes of this demo. Run: demo.py record <slug>"""
from kit import card, scene, skip

APP = "http://localhost:3000"

card("00", kicker="Product name", title="The problem, in <em>1 line</em>.", sub="What the viewer will see.", seconds=5)


@scene("01", "What this scene shows")
def first(d):
    d.goto(APP)
    button = d.page.get_by_role("button", name="New")
    d.ring(button, zoom=1.3)
    d.click(button)
    d.focus(d.page.get_by_role("dialog"), zoom=1.2)
    d.type("Example")
    d.wait(1.0)
'''


def init(out: Path) -> None:
    (out / "narration").mkdir(parents=True, exist_ok=True)
    scenes = out / "scenes.py"
    if not scenes.exists():
        scenes.write_text(TEMPLATE)
    print(out)


def speak(*args: str) -> bool:
    """Runs Kokoro: with uv when there is one, else with this Python and pip."""
    if shutil.which("uv"):
        return _uv("speak.py", *args) == 0
    # A failed install shows in the run below, which then returns False.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "kokoro>=0.9", "soundfile"],
        check=False,
    )
    script = [sys.executable, str(HERE / "speak.py"), *args]
    return subprocess.run(script, check=False).returncode == 0


def _uv(script: str, *args: str) -> int:
    """Runs a script of this folder in its own uv environment; its exit code."""
    if not shutil.which("uv"):
        sys.exit(f"{script} runs with uv, and this machine has none: see setup.md")
    command = ["uv", "run", "--quiet", str(HERE / script), *args]
    return subprocess.run(command, check=False).returncode


def narrate(out: Path, speed: float, voice: str) -> None:
    """Kokoro, a local voice model; when it cannot run, the macOS `say` voice."""
    texts = sorted((out / "narration").glob("*.txt"))
    if not texts:
        sys.exit(f"no narration/NN.txt in {out}")
    if voice == "me":
        if _uv("clone.py", "speak", str(out / "narration")):
            sys.exit("the voice clone did not run: see the error above")
        print("narrator: your voice, Qwen3-TTS clone")
        return
    if speak(str(out / "narration"), "--voice", voice, "--speed", str(speed)):
        print(f"narrator: Kokoro, {voice}, speed {speed}")
        return
    if not shutil.which("say"):
        sys.exit("no narrator: fix Kokoro, or put narration/NN.wav there by hand")
    for text in texts:
        subprocess.run(
            ["say", "-r", str(int(175 * speed)), "-o"]
            + [str(text.with_suffix(".aiff")), "-f", str(text)],
            check=True,
        )
    print("narrator: macOS say (Kokoro did not run; pauses and voices need Kokoro)")


def clone(recording: str | None, text: str | None) -> None:
    """Saves the user's voice sample: a file, or 15 s from the microphone now."""
    sys.path.insert(0, str(HERE))
    from clone import PASSAGE

    if not recording:
        sys.exit(
            f"give a recording, or `record` to use the microphone. Read this:\n{PASSAGE}"
        )
    if recording == "record":
        from media import ffmpeg, run

        recording = str(ROOT / "voice-take.wav")
        print(f"recording 15 s. Read this aloud now:\n\n  {PASSAGE}\n", flush=True)
        run(
            [ffmpeg(), "-v", "error", "-y", "-f", "avfoundation", "-i", ":0"]
            + ["-t", "15", recording]
        )
        text = PASSAGE
    extra = ["--text", text] if text else []
    code = _uv("clone.py", "keep", recording, *extra)
    if code:
        sys.exit(code)


def voices(text: str | None) -> None:
    """Writes 1 sample per voice, so the user can listen and pick."""
    extra = ["--text", text] if text else []
    if not speak(str(ROOT / "voices"), "--samples", *extra):
        sys.exit("Kokoro did not run")


def selftest() -> None:
    import build
    import check
    import edit
    import kit

    out = ROOT / "selftest"
    if out.exists():
        out.rename(ROOT / f"selftest-old-{int(out.stat().st_mtime)}")
    out.mkdir(parents=True)
    source = (HERE / "selftest" / "scenes.py").read_text()
    (out / "scenes.py").write_text(
        source.replace("PAGE_URL", (HERE / "selftest" / "page.html").as_uri())
    )
    kit.record(out, None)
    edit.edit(out, "product")
    build.build(out, None)
    check.check(out)


def doctor(url: str | None) -> None:
    """Prints what this machine has, then the path to take: record or screen.

    record: this machine drives a browser on the app (Claude Code).
    screen: the user's own screen recorder films; this machine finishes the
    video (a claude.ai or Cowork sandbox, or a native app).
    """
    import urllib.error
    import urllib.request

    def line(name: str, ok: bool, detail: str) -> bool:
        print(f"{'ok  ' if ok else 'no  '}  {name:<9} {detail}")
        return ok

    try:
        from media import ffmpeg

        video = line("ffmpeg", True, ffmpeg())
    except SystemExit as error:
        video = line("ffmpeg", False, f"{error}")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            path = Path(p.chromium.executable_path)
        line(
            "chromium",
            path.exists(),
            str(path)
            if path.exists()
            else "not downloaded: the first `record` does it",
        )
        browser = True  # `record` downloads it, about 150 MB
    except Exception as error:  # noqa: BLE001 - any failure here is a "no" line
        browser = line("chromium", False, f"playwright did not load: {error}")
    reach = True
    if url:
        try:
            with urllib.request.urlopen(url, timeout=10) as answer:
                line("app", True, f"{url} answered {answer.status}")
        except urllib.error.HTTPError as error:
            line("app", True, f"{url} answered {error.code}: sign in with `login`")
        except Exception as error:  # noqa: BLE001 - any failure here is a "no" line
            reach = line("app", False, f"{url} did not answer: {error}")
    uv = shutil.which("uv")
    line(
        "kokoro",
        True,
        "through uv" if uv else "through pip: the first `narrate` installs it",
    )
    sample = Path.home() / ".config/demo-video/voice/sample.wav"
    mac = sys.platform == "darwin" and os.uname().machine == "arm64"
    line(
        "your voice",
        mac and sample.exists(),
        "saved: `narrate --voice me`"
        if mac and sample.exists()
        else "`demo clone` saves it"
        if mac
        else "needs a Mac with Apple silicon and Claude Code",
    )
    line("say", bool(shutil.which("say")), "the narrator when Kokoro fails")
    if not video:
        sys.exit("path: none. Install ffmpeg, or `pip install imageio-ffmpeg`")
    if not browser:
        print("path: screen (read SCREEN.md)")
    elif reach:
        print("path: record")
    else:
        sys.exit("path: record, once the app answers: start it")


# claude.ai rejects a SKILL.md whose frontmatter has a key outside this set.
PORTABLE = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}


def overlay() -> None:
    """Prints the drawn cursor that follows the clicks of a browser tool.

    Claude in Chrome clicks a page without the real mouse, so the user's
    recorder would film no pointer. Run the printed script in the page after
    each page load; the cursor keeps its place across loads.
    """
    print((HERE / "overlay.js").read_text().rstrip() + "\nwindow.__demo.follow();")


def package(target: str | None) -> None:
    """Zips the skill folder for the claude.ai upload: 1 folder named like the skill."""
    import re
    import zipfile

    skill = HERE.parent
    head = (skill / "SKILL.md").read_text().split("---")[1]
    keys = set(re.findall(r"^([\w-]+):", head, re.MULTILINE))
    if keys - PORTABLE:
        sys.exit(f"SKILL.md has keys claude.ai rejects: {sorted(keys - PORTABLE)}")
    zipped = Path(target or ROOT / f"{skill.name}.zip").expanduser().resolve()
    zipped.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zipped, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(skill.rglob("*")):
            inside = path.relative_to(skill)
            # Caches and hidden files: __pycache__, .ruff_cache, .DS_Store.
            if path.is_file() and not any(
                part.startswith((".", "__")) for part in inside.parts
            ):
                archive.write(path, Path(skill.name) / inside)
    print(zipped, f"{zipped.stat().st_size / 1024:.0f} KB")


def _call(module: str, function: str, *args, **kwargs) -> None:
    """Imports a step only when it runs: doctor and narrate work without Playwright."""
    getattr(import_module(module), function)(*args, **kwargs)


def _slug(args: argparse.Namespace) -> str:
    if not args.slug:
        PARSER.error(f"{args.command} needs a slug, a url or a file")
    return args.slug


def _out(args: argparse.Namespace, made: bool = True) -> Path:
    """The work folder that the slug names; `made`: it must exist already."""
    out = folder(_slug(args))
    if made and not out.exists():
        sys.exit(f"{out} does not exist: run `demo.py init {args.slug}` first")
    return out


def _extra(args: argparse.Namespace, what: str) -> str:
    if not args.extra:
        PARSER.error(f"{args.command} needs {what}")
    return args.extra


def _names(args: argparse.Namespace) -> list[str] | None:
    return args.extra.split(",") if args.extra else None


COMMANDS = {
    "init": lambda a: init(_out(a, made=False)),
    "login": lambda a: _call("kit", "login", _out(a), _extra(a, "the url of the app")),
    "narrate": lambda a: narrate(_out(a), a.speed, a.voice),
    "voices": lambda a: voices(a.slug),
    "clone": lambda a: clone(a.slug, a.extra),
    "record": lambda a: _call(
        "kit", "record", _out(a), _names(a), scale=a.scale, headed=a.headed
    ),
    "edit": lambda a: _call("edit", "edit", _out(a), a.mode),
    "build": lambda a: _call("build", "build", _out(a), _names(a)),
    "check": lambda a: _call("check", "check", _out(a)),
    "study": lambda a: _call("check", "study", _slug(a), ROOT / "study"),
    "selftest": lambda a: selftest(),
    "doctor": lambda a: doctor(a.slug),
    "package": lambda a: package(a.slug),
    "mark": lambda a: _call(
        "screen", "mark", _out(a), _extra(a, "a scene number, or `start`"), a.more
    ),
    "finish": lambda a: _call(
        "screen",
        "finish",
        _out(a),
        Path(_extra(a, "the path of the screen recording")).expanduser(),
        a.offset,
    ),
    "overlay": lambda a: overlay(),
}

PARSER = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
PARSER.add_argument("command", choices=list(COMMANDS))
PARSER.add_argument("slug", nargs="?")
PARSER.add_argument("extra", nargs="?")
PARSER.add_argument("more", nargs="?")
PARSER.add_argument(
    "--offset",
    type=float,
    help="finish: seconds into the recording at which the first mark falls",
)
PARSER.add_argument("--mode", choices=["demo", "product"], default="demo")
PARSER.add_argument("--speed", type=float, default=1.0, help="narration speed")
PARSER.add_argument(
    "--voice",
    default="af_heart",
    help="a voice name from `demo.py voices`, or `me` after `demo.py clone`",
)
PARSER.add_argument(
    "--scale",
    type=int,
    default=2,
    help="device pixels per page pixel: 2 allows 1.67x zoom, 3 allows 2.5x",
)
PARSER.add_argument(
    "--headed", action="store_true", help="show the browser while it records"
)


def main() -> None:
    args = PARSER.parse_args()
    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
