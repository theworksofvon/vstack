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
from pathlib import Path

HERE = Path(__file__).parent
ROOT = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "vstack/demo-video"
)

TEMPLATE = '''"""The scenes of this demo. Run: demo.py record <slug>"""
from kit import card, scene, skip

APP = "http://localhost:3000"

card("00", kicker="Product name", title="The problem, in <em>1 line</em>.", sub="What the viewer will see.", seconds=5)


@scene("01", "What this scene shows")
def first(d):
    d.goto(APP)
    button = d.page.get_by_role("button", name="New")
    d.ring(button, "Start here", zoom=1.3)
    d.click(button)
    d.focus(d.page.get_by_role("dialog"), zoom=1.2)
    d.type("Example")
    d.wait(1.0)
'''


def folder(slug: str) -> Path:
    path = Path(slug).expanduser() if "/" in slug else ROOT / slug
    return path.resolve()


def init(out: Path) -> None:
    (out / "narration").mkdir(parents=True, exist_ok=True)
    scenes = out / "scenes.py"
    if not scenes.exists():
        scenes.write_text(TEMPLATE)
    print(out)


def speak(*args: str) -> bool:
    """Runs Kokoro: with uv when there is one, else with this Python and pip."""
    if shutil.which("uv"):
        run = ["uv", "run", "--quiet", str(HERE / "speak.py")]
    else:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "kokoro>=0.9", "soundfile"]
        )
        run = [sys.executable, str(HERE / "speak.py")]
    return subprocess.run([*run, *args]).returncode == 0


def narrate(out: Path, speed: float, voice: str) -> None:
    """Kokoro, a local voice model; when it cannot run, the macOS `say` voice."""
    texts = sorted((out / "narration").glob("*.txt"))
    if not texts:
        sys.exit(f"no narration/NN.txt in {out}")
    if voice == "me":
        done = subprocess.run(
            [
                "uv",
                "run",
                "--quiet",
                str(HERE / "clone.py"),
                "speak",
                str(out / "narration"),
            ]
        )
        if done.returncode:
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
        from media import ffmpeg

        recording = str(ROOT / "voice-take.wav")
        print(f"recording 15 s. Read this aloud now:\n\n  {PASSAGE}\n", flush=True)
        subprocess.run(
            [ffmpeg(), "-v", "error", "-y", "-f", "avfoundation", "-i", ":0"]
            + ["-t", "15", recording],
            check=True,
        )
        text = PASSAGE
    extra = ["--text", text] if text else []
    done = subprocess.run(
        ["uv", "run", "--quiet", str(HERE / "clone.py"), "keep", recording, *extra]
    )
    if done.returncode:
        sys.exit(done.returncode)


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
        browser = line(
            "chromium",
            path.exists(),
            str(path)
            if path.exists()
            else "not downloaded: the first `record` does it",
        )
        browser = True  # `record` downloads it, about 150 MB
    except Exception as error:
        browser = line("chromium", False, f"playwright did not load: {error}")
    reach = True
    if url:
        try:
            with urllib.request.urlopen(url, timeout=10) as answer:
                line("app", True, f"{url} answered {answer.status}")
        except urllib.error.HTTPError as error:
            line("app", True, f"{url} answered {error.code}: sign in with `login`")
        except Exception as error:
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
    keys = set(re.findall(r"^([\w-]+):", head, re.M))
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command",
        choices=[
            "init",
            "login",
            "narrate",
            "voices",
            "clone",
            "record",
            "edit",
            "build",
            "check",
            "study",
            "selftest",
            "doctor",
            "package",
            "mark",
            "finish",
            "overlay",
        ],
    )
    parser.add_argument("slug", nargs="?")
    parser.add_argument("extra", nargs="?")
    parser.add_argument("more", nargs="?")
    parser.add_argument(
        "--offset",
        type=float,
        help="finish: seconds into the recording at which the first mark falls",
    )
    parser.add_argument("--mode", choices=["demo", "product"], default="demo")
    parser.add_argument("--speed", type=float, default=1.0, help="narration speed")
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="a voice name from `demo.py voices`, or `me` after `demo.py clone`",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=2,
        help="device pixels per page pixel: 2 allows 1.67x zoom, 3 allows 2.5x",
    )
    parser.add_argument(
        "--headed", action="store_true", help="show the browser while it records"
    )
    args = parser.parse_args()

    if args.command == "selftest":
        return selftest()
    if args.command == "doctor":
        return doctor(args.slug)
    if args.command == "overlay":
        return overlay()
    if args.command == "package":
        return package(args.slug)
    if args.command == "clone":
        return clone(args.slug, args.extra)
    if args.command == "voices":
        return voices(args.slug)
    if not args.slug:
        parser.error(f"{args.command} needs a slug, a url or a file")
    if args.command == "study":
        import check

        return check.study(args.slug, ROOT / "study")
    out = folder(args.slug)
    if args.command == "init":
        return init(out)
    if not out.exists():
        sys.exit(f"{out} does not exist: run `demo.py init {args.slug}` first")
    names = args.extra.split(",") if args.extra else None
    if args.command == "login":
        if not args.extra:
            parser.error("login needs the url of the app")
        import kit

        kit.login(out, args.extra)
    elif args.command == "mark":
        import screen

        if not args.extra:
            parser.error("mark needs a scene number, or `start`")
        screen.mark(out, args.extra, args.more)
    elif args.command == "finish":
        import screen

        if not args.extra:
            parser.error("finish needs the path of the screen recording")
        screen.finish(out, Path(args.extra).expanduser(), args.offset)
    elif args.command == "narrate":
        narrate(out, args.speed, args.voice)
    elif args.command == "record":
        import kit

        kit.record(out, names, scale=args.scale, headed=args.headed)
    elif args.command == "edit":
        import edit

        edit.edit(out, args.mode)
    elif args.command == "build":
        import build

        build.build(out, names)
    elif args.command == "check":
        import check

        check.check(out)


if __name__ == "__main__":
    main()
