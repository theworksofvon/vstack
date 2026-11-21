"""The recorder: drives a real browser through scenes and saves each frame.

A scenes file imports `scene`, `card` and `skip` from here. `demo.py record`
loads that file and runs it.

Times are "video time": `d.cut()` removes a wait from the video, and
`d.fast_forward()` divides it. The page is never scaled: `d.focus()` only
writes a camera note, and the build step crops the frames.
"""

import base64
import contextlib
import html
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from camera import Note, aim
from playwright.sync_api import Locator, Page, sync_playwright
from work import Take, profile, retire

HERE = Path(__file__).parent
WIDTH, HEIGHT = 1600, 900
# A session renewed this recently is still good: 5 min, a guess that covers
# the start of every scene agent in 1 parallel round.
FRESH = 300

SIGN_IN = 20 * 60  # seconds the sign-in window waits for the user


@dataclass(frozen=True)
class Scene:
    run: Callable[["Demo"], None]
    caption: str | None


@dataclass(frozen=True)
class Card:
    title: str
    sub: str
    kicker: str
    seconds: float


SCENES: dict[str, Scene | Card] = {}


class Skip(Exception):
    """Raised by a scene that cannot run; the frames it wrote are discarded.

    An earlier take of the scene stays in `frames/NN`.
    """


def skip(reason: str) -> None:
    raise Skip(reason)


def scene(name: str, caption: str | None = None):
    """Registers a scene. `caption` shows for the first seconds of the scene."""

    def register(run):
        SCENES[name] = Scene(run, caption)
        return run

    return register


def card(
    name: str, title: str, sub: str = "", kicker: str = "", seconds: float = 6.0
) -> None:
    """Registers a title card. `title` can hold <em> for the accent colour."""
    SCENES[name] = Card(title, sub, kicker, seconds)


class Recorder:
    """Saves screencast frames with a video clock that can pause or run fast.

    Also keeps what the later steps need: the clicks and keys for sound, the
    camera notes, the fast-forward spans and the caption.
    """

    def __init__(self, page: Page, out: Path, scale: int):
        self.page = page
        self.out = out
        self.scale = scale
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.dir: Path | None = None
        self.name = ""
        self.rate = 1.0
        self.clock = 0.0
        self.last: float | None = None
        self._reset()

    def _reset(self) -> None:
        self.frames: list[tuple[str, float]] = []
        self.events: list[dict] = []
        self.camera: list[Note] = []
        self.fast: list[list[float]] = []
        self.caption: list[str] | None = None
        self.is_card = False

    def _advance(self) -> None:
        now = time.monotonic()
        if self.last is not None and self.rate > 0:
            self.clock += (now - self.last) / self.rate
        self.last = now

    def now(self) -> float:
        self._advance()
        return self.clock

    def _frame(self, event: dict) -> None:
        self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        if self.dir is None or self.rate <= 0:
            return
        self._advance()
        name = f"{len(self.frames):06d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(event["data"]))
        self.frames.append((name, self.clock))

    def start(self, name: str) -> None:
        # A take records beside the last good one, and replaces it only in
        # `stop`: a take that fails or skips leaves the good one in place.
        self.name = name
        self.dir = self.out / "frames" / f"{name}.take-{os.getpid()}"
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self._reset()
        self.clock, self.last, self.rate = 0.0, time.monotonic(), 1.0
        self.cdp.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 92, "everyNthFrame": 1},
        )
        self.poke()

    def set_rate(self, rate: float) -> None:
        """1 is real time, 8 is 8 times as fast, 0 pauses."""
        self._advance()
        self.rate = rate
        if rate > 0:
            self.poke()

    def event(self, kind: str) -> None:
        """A sound cue at this moment: click or key."""
        if self.dir is not None and self.rate == 1:
            self.events.append({"t": self.now(), "kind": kind})

    def poke(self) -> None:
        # A still page sends no frame: this changes 4 pixels, so one arrives.
        self.page.evaluate("window.__demo && window.__demo.tick()")

    def stop(self, keep: bool = True) -> None:
        self.poke()
        self.page.wait_for_timeout(250)
        self._advance()
        self.cdp.send("Page.stopScreencast")
        assert self.dir is not None
        if not keep:
            self.abandon()
            return
        Take(
            frames=self.frames,
            end=self.clock,
            events=self.events,
            camera=self.camera,
            fast=self.fast,
            caption=self.caption,
            card=self.is_card,
            size=[WIDTH, HEIGHT],
            scale=self.scale,
        ).save(self.dir / "manifest.json")
        print(
            f"{self.name}: {len(self.frames)} frames, {self.clock:.1f} s, "
            f"{len(self.events)} sounds, {len(self.camera)} camera moves",
            flush=True,
        )
        retire(self.out, self.name)
        self.dir.rename(self.out / "frames" / self.name)
        self.dir = None

    def abandon(self) -> None:
        """Drops the take that runs now; an earlier take of the scene stays."""
        if self.dir is None:
            return
        with contextlib.suppress(Exception):  # the page can be gone already
            self.cdp.send("Page.stopScreencast")
        shutil.rmtree(self.dir)
        self.dir = None
        if (self.out / "frames" / self.name).exists():
            print(f"{self.name}: kept the earlier take", flush=True)


class Demo:
    """What a scene calls. `d.page` is the Playwright page for anything else."""

    def __init__(self, page: Page, rec: Recorder):
        self.page = page
        self.rec = rec
        self.fast = False
        # The camera of the build step: its centre in page pixels, and its zoom.
        self.cam = (WIDTH / 2, HEIGHT / 2, 1.0)

    # --- pacing ---

    def goto(self, url: str) -> None:
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

    def wait(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * (250 if self.fast else 1000)))

    def until(self, mark: float) -> None:
        """Holds until the scene's video clock reaches `mark` seconds."""
        now = self.rec.now()
        if now < mark:
            self.page.wait_for_timeout(int((mark - now) * 1000))

    @contextlib.contextmanager
    def cut(self):
        """The time inside this block is not in the video: a load, a long job."""
        self.rec.set_rate(0)
        try:
            yield
        finally:
            self.rec.set_rate(1)

    @contextlib.contextmanager
    def fast_forward(self, label: str, rate: float = 10):
        """The block plays `rate` times as fast, with `label` shown as a badge."""
        self.wide(0.6)
        self.page.evaluate("(t) => __demo.speed(t)", label)
        self.wait(0.4)
        start = self.rec.now()
        self.rec.set_rate(rate)
        self.fast = True
        try:
            yield
        finally:
            self.fast = False
            self.rec.set_rate(1)
            self.rec.fast.append([start, self.rec.now()])
            self.page.evaluate("__demo.speed(null)")

    # --- camera: notes for the build step, the page does not change ---

    def _camera(self, cx: float, cy: float, zoom: float, seconds: float) -> None:
        cx, cy, zoom = aim(cx, cy, zoom, (WIDTH, HEIGHT), self.rec.scale)
        if (cx, cy, zoom) == self.cam:
            return
        self.cam = (cx, cy, zoom)
        self.rec.camera.append(Note(self.rec.now(), cx, cy, zoom, seconds))

    def focus(
        self,
        target: Locator,
        zoom: float = 1.4,
        seconds: float = 0.8,
        dx: float = 0.5,
        dy: float = 0.5,
    ) -> None:
        """Moves the camera in on `target`. `zoom` stops at the sharpness limit."""
        if self.fast or not target.count():
            return
        self.settle(target)
        box = target.bounding_box()
        if box:
            self._camera(
                box["x"] + box["width"] * dx,
                box["y"] + box["height"] * dy,
                zoom,
                seconds,
            )

    def wide(self, seconds: float = 0.8) -> None:
        self._camera(WIDTH / 2, HEIGHT / 2, 1.0, seconds)

    def _follow(self, x: float, y: float) -> None:
        """Pans a zoomed camera when the pointer goes near the view's edge."""
        cx, cy, zoom = self.cam
        if zoom == 1 or self.fast:
            return
        half_w, half_h = WIDTH / zoom / 2, HEIGHT / zoom / 2
        if abs(x - cx) > half_w * 0.62 or abs(y - cy) > half_h * 0.55:
            self._camera(x, y, zoom, 0.7)

    # --- overlay ---

    def notice(self, title: str | None, detail: str | None = None) -> None:
        if title:
            self.wide(0.6)
        self.page.evaluate("([t, d]) => __demo.notice(t, d)", [title, detail])

    def ring(
        self,
        target: Locator,
        label: str | None = None,
        hold: float = 1.6,
        below: bool = False,
        zoom: float | None = None,
    ) -> None:
        """Draws a ring with `label` round `target`, for `hold` seconds."""
        if not target.count():
            print("ring skipped:", label, flush=True)
            return
        self.settle(target)
        if zoom:
            self.focus(target, zoom)
            self.wait(0.5)
        box = target.bounding_box()
        if not box:
            return
        self.page.evaluate(
            "([r, l, b]) => { __demo.ring(r, l, b) }", [box, label, below]
        )
        self.wait(hold)
        self.page.evaluate("__demo.clearRings()")
        self.wait(0.3)

    # --- pointer ---

    def show(self, target: Locator) -> None:
        """Scrolls `target` into the middle of its scroll container, smoothly."""
        visible = target.evaluate(
            """(el) => {
              const r = el.getBoundingClientRect();
              const view = { top: 70, bottom: innerHeight - 120 };
              for (let p = el.parentElement; p; p = p.parentElement) {
                const s = getComputedStyle(p).overflowY;
                if ((s === 'auto' || s === 'scroll') && p.scrollHeight > p.clientHeight) {
                  // Scroll only this container: scrollIntoView also moves the page.
                  const pr = p.getBoundingClientRect();
                  const top = Math.max(view.top, pr.top + 10);
                  const bottom = Math.min(view.bottom, pr.bottom - 10);
                  if (r.top >= top && r.bottom <= bottom) return true;
                  const delta = r.top + r.height / 2 - (top + bottom) / 2;
                  p.scrollTo({ top: p.scrollTop + delta, behavior: 'smooth' });
                  return false;
                }
              }
              if (r.top >= 0 && r.bottom <= innerHeight) return true;
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
              return false;
            }"""
        )
        if not visible:
            self.wait(0.3)
        self.settle(target)

    def settle(self, target: Locator) -> None:
        """Waits until `target` stops moving: a scroll, or a panel that opens."""
        last = None
        for _ in range(25):
            box = target.bounding_box()
            if (
                box
                and last
                and abs(box["y"] - last["y"]) < 0.5
                and abs(box["x"] - last["x"]) < 0.5
            ):
                return
            last = box
            self.page.wait_for_timeout(110)

    def point(self, target: Locator, ms: int = 600, dx: float = 0.5, dy: float = 0.5):
        """Moves the drawn cursor to `target`."""
        self.show(target)
        box = target.bounding_box()
        assert box, "target has no box"
        x = box["x"] + box["width"] * dx
        y = box["y"] + box["height"] * dy
        ms = 150 if self.fast else ms
        self._follow(x, y)
        self.page.evaluate("([x, y, ms]) => __demo.move(x, y, ms)", [x, y, ms])
        self.page.wait_for_timeout(ms + 60)
        self.page.mouse.move(x, y)
        return x, y

    def click(
        self, target: Locator, before: float = 0.25, after: float = 0.6, **where
    ) -> None:
        x, y = self.point(target, **where)
        self.wait(before)
        self.page.evaluate("([x, y]) => __demo.ripple(x, y)", [x, y])
        self.rec.event("click")
        self.page.mouse.click(x, y)
        self.wait(after)

    def type(self, text: str, delay: int = 85) -> None:
        """Types into the element that has the keyboard focus."""
        if self.fast:
            self.page.keyboard.type(text, delay=20)
            return
        for char in text:
            self.page.keyboard.type(char)
            if char != " ":
                self.rec.event("key")
            self.page.wait_for_timeout(delay)

    def shot(self, name: str) -> None:
        (self.rec.out / "shots").mkdir(exist_ok=True)
        self.page.screenshot(path=str(self.rec.out / "shots" / f"{name}.png"))


def _card_page(out: Path, name: str, spec: Card) -> Path:
    parts = [
        '<!doctype html><meta charset="utf-8">',
        f"<style>{(HERE / 'card.css').read_text()}</style>",
        '<div class="grid"></div>',
    ]
    if spec.kicker:
        parts.append(
            f'<div class="kicker a" style="--d:.1s">{html.escape(spec.kicker)}</div>'
        )
    parts.append(f'<h1 class="a" style="--d:.35s">{spec.title}</h1>')
    if spec.sub:
        parts.append(
            f'<div class="sub a" style="--d:1.3s">{html.escape(spec.sub)}</div>'
        )
    path = out / "cards" / f"{name}.html"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(parts))
    return path


def _run_card(d: Demo, name: str, spec: Card) -> None:
    d.page.goto(_card_page(d.rec.out, name, spec).as_uri())
    d.page.evaluate("__demo.move(-200, -200, 0)")
    d.page.wait_for_timeout(400)
    d.rec.start(name)
    d.rec.is_card = True
    try:
        d.page.evaluate("document.body.classList.add('go')")
        d.page.wait_for_timeout(int(spec.seconds * 1000))
    except BaseException:
        d.rec.abandon()
        raise
    d.rec.stop()


def _run_scene(d: Demo, name: str, spec: Scene, number: int) -> None:
    d.cam = (WIDTH / 2, HEIGHT / 2, 1.0)
    d.rec.start(name)
    if spec.caption:
        d.rec.caption = [str(number), spec.caption]
    try:
        spec.run(d)
    except Skip as reason:
        print(f"{name}: skipped, {reason}", flush=True)
        d.rec.stop(keep=False)
        return
    except BaseException:
        d.rec.abandon()
        raise
    d.wide(0.7)
    d.wait(0.9)
    d.rec.stop()


def _launch(start, *args, **kwargs):
    """Starts Chromium. The first run on a machine downloads it, about 150 MB."""
    try:
        return start(*args, **kwargs)
    except Exception as error:
        if "Executable doesn't exist" not in str(error):
            raise
        print("first run: downloading Chromium for Playwright", flush=True)
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"], check=True
        )
        return start(*args, **kwargs)


def load(scenes_file: Path) -> tuple[dict[str, Scene | Card], list[Path]]:
    """The scenes that registered, and the files that failed to load.

    scenes.py, then each scene_NN.py beside it: 1 file per scene lets 1
    agent own it, so an error in another agent's file only skips that file.
    """
    SCENES.clear()
    sys.path.insert(0, str(scenes_file.parent))
    files = [scenes_file, *sorted(scenes_file.parent.glob("scene_*.py"))]
    broken = [path for path in files if path.exists() and not _import(path)]
    return dict(SCENES), broken


def _import(path: Path) -> bool:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # noqa: BLE001 - a scene file can raise anything
        print(f"{path.name}: not loaded, {type(error).__name__}: {error}", flush=True)
        return False
    return True


def record(
    out: Path, names: list[str] | None, scale: int = 2, headed: bool = False
) -> None:
    """Records the scenes of `out/scenes.py`, in the order of `names`."""
    scenes, broken = load(out / "scenes.py")
    if not names and broken:
        sys.exit(
            f"{[p.name for p in broken]} did not load: fix them, or name the scenes to record"
        )
    names = names or sorted(scenes)
    missing = [n for n in names if n not in scenes]
    if missing:
        sys.exit(f"no scene named {missing}; the scene files have {sorted(scenes)}")
    (out / "scenes.json").write_text(json.dumps(sorted(scenes)))
    refresh(out)
    state = out / "state.json"
    numbers = {
        n: i + 1
        for i, n in enumerate(n for n in sorted(scenes) if isinstance(scenes[n], Scene))
    }
    with sync_playwright() as p:
        browser = _launch(
            p.chromium.launch,
            channel="chromium",
            headless=not headed,
            args=[
                f"--force-device-scale-factor={scale}",
                # The window frame takes 87 px of the height.
                f"--window-size={WIDTH},{HEIGHT + 87}",
                "--hide-scrollbars",
            ],
        )
        context = browser.new_context(
            storage_state=str(state) if state.exists() else None, no_viewport=True
        )
        context.add_init_script(path=str(HERE / "overlay.js"))
        page = context.new_page()
        demo = Demo(page, Recorder(page, out, scale))
        try:
            for name in names:
                if isinstance(scenes[name], Card):
                    _run_card(demo, name, scenes[name])
                else:
                    _run_scene(demo, name, scenes[name], numbers[name])
        finally:
            (out / "shots").mkdir(exist_ok=True)
            page.screenshot(path=str(out / "shots" / "last.png"))
            # Per scene too: 2 recordings at the same time share last.png.
            shutil.copy(out / "shots" / "last.png", out / "shots" / f"{names[-1]}.png")
            if state.exists():
                _save(context, state)
            browser.close()


def login(out: Path, url: str) -> None:
    """Saves a signed-in session for `url` to `out/state.json`.

    1 browser profile per app keeps the identity provider's own cookie,
    which lasts weeks; the app's session is shorter. So the sign-in first
    runs without a window, and asks the user only when that fails.
    """
    (out / "login.txt").write_text(url)
    with _turn(profile(url)):
        if _silent(out, url):
            print("signed in without a window:", out / "state.json", flush=True)
            return
        _window(out, url)


def _window(out: Path, url: str) -> None:
    """Waits for the user to sign in to `url` in a browser window."""
    with sync_playwright() as p:
        context = _launch(
            p.chromium.launch_persistent_context,
            str(profile(url)),
            channel="chromium",
            headless=False,
            viewport={"width": 1100, "height": 800},
        )
        # The user has their own Chrome open too: name this window.
        context.add_init_script(
            "addEventListener('DOMContentLoaded', () => "
            "{ document.title = 'SIGN IN HERE (demo-video) · ' + document.title })"
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        if shutil.which("osascript"):
            # The window opens behind the Claude app: bring it to the front.
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "Google Chrome for Testing" to activate',
                ],
                check=False,
            )
        print(
            "sign in in the window titled SIGN IN HERE; it closes when the app shows",
            flush=True,
        )
        deadline, seen = time.time() + SIGN_IN, None
        while time.time() < deadline:
            urls = [candidate.url for candidate in context.pages]
            where = " ".join(u.split("?")[0] for u in urls)
            if where != seen:
                print("  at", where, flush=True)
                if "/consent" in where:
                    print(
                        "  the window asks to authorize the app: click Accept",
                        flush=True,
                    )
                seen = where
            if any(_in_app(u, url) for u in urls):
                time.sleep(2)
                _renew(context, out)
                print("signed in:", out / "state.json", flush=True)
                context.close()
                return
            time.sleep(1)
        context.close()
        sys.exit(f"no sign-in before the deadline; the window was at {seen}")


def refresh(out: Path) -> None:
    """Renews the session before a recording, without a window, when it can.

    Scene agents record at the same time and share 1 profile per app, which
    only 1 browser can open. So they take turns, and an agent skips the
    renewal when another one renewed the session in the last FRESH seconds.
    A recording also saves state.json, so the renewal time is kept apart, in
    `renewed`, which only a sign-in writes.
    """
    saved = out / "login.txt"
    if not saved.exists():
        return
    url = saved.read_text().strip()
    renewed = out / "renewed"
    with _turn(profile(url)):
        if renewed.exists() and time.time() - renewed.stat().st_mtime < FRESH:
            return
        if not _silent(out, url):
            sys.exit("the saved sign-in ran out: run `demo login` to sign in again")


@contextlib.contextmanager
def _turn(profile: Path):
    """Holds the profile's lock file until the block ends."""
    try:
        import fcntl
    except ImportError:  # Windows: no lock, as before
        yield
        return
    profile.parent.mkdir(parents=True, exist_ok=True)
    with (profile.parent / f"{profile.name}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _save(context, state: Path) -> None:
    """Writes the session in 1 step, so a recording that reads it at the same
    time never gets half a file."""
    fresh = state.with_name(f"state.{os.getpid()}.json")
    context.storage_state(path=str(fresh))
    fresh.replace(state)


def _renew(context, out: Path) -> None:
    _save(context, out / "state.json")
    (out / "renewed").touch()


def _in_app(page_url: str, url: str) -> bool:
    origin = "/".join(url.split("/")[:3])
    path = page_url[len(origin) :].split("?")[0]
    return page_url.startswith(origin) and not path.startswith(
        ("/auth", "/login", "/callback", "/signin", "/sign-in")
    )


def _silent(out: Path, url: str) -> bool:
    """Opens the app's profile without a window; True when the app shows."""
    try:
        with sync_playwright() as p:
            context = _launch(
                p.chromium.launch_persistent_context,
                str(profile(url)),
                channel="chromium",
                headless=True,
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=45_000)
            inside = _in_app(page.url, url)
            if inside:
                _renew(context, out)
            context.close()
            return inside
    except Exception as error:  # noqa: BLE001 - a profile in use, a timeout
        print(f"no sign-in without a window: {str(error).splitlines()[0]}", flush=True)
        return False
