"""A screen recording made on the user's computer, turned into scenes.

The other path: when the agent cannot run the recorder (a claude.ai or
Cowork sandbox), the user's own screen recorder films the walk-through,
and this step writes the same `frames/NN/manifest.json` that `record`
writes. `edit`, `build` and `check` then run as usual.

  mark    the agent stamps the start of each scene in `marks.jsonl` while
          it drives the app; the sandbox clock is close to the computer's
  finish  keeps only the frames that change (a screencast does the same),
          shortens the still time while the agent thought, splits the
          scenes at the marks, and puts a click sound and a zoom on each
          burst of change
"""

import json
import re
import shutil
import time
from datetime import datetime
from itertools import pairwise
from pathlib import Path

import numpy as np
from camera import OUTPUT, Note, aim
from media import log, pts, seconds
from PIL import Image
from work import Take, narrated, retire

SAMPLE = 30  # frames per second taken from the recording; the build sets its own
WIDTH, HEIGHT = OUTPUT  # page pixels of the frames: 1 page pixel per output pixel
SHARP = 2  # frames are WIDTH * SHARP wide, so a 2x zoom stays sharp
LOOK = (480, 270)  # the size each frame is compared at
DIFF = 28  # a pixel that changes by more than 28 of 255 has changed
STILL = 1.0  # seconds with no change before a burst counts as a new action
KEEP = 0.7  # seconds of a still gap that stay in the video
SLACK = 1.5  # seconds a mark can fall outside its still gap: the clocks differ a little
CARET = 14  # changed pixels, of LOOK: a caret blink measured 8 to 10, a typed letter 19 to 27
ZOOM = 1.5  # the zoom on a small change
LEAST = 1.2  # the least zoom worth a camera move
FILL = 0.5  # a zoom shows a change at about half the view's width and height
TINY = 0.01  # the smallest changed area a zoom is sized for: a caret, a dot
NOTICED = 20  # changed pixels, of LOOK, that a viewer sees as a result
LEAD = 0.3  # seconds the camera starts before the click it goes to
IN, OUT = 0.8, 0.7  # seconds a zoom in and a zoom back out take
AFTER = 0.8  # seconds the scene runs after its last zoom out starts
LONGEST = 3.0  # the longest pause between 2 actions, however long the narration
HOLD = 1.2  # seconds the zoomed result stays on screen before the camera goes wide
SMALL = 0.35  # a change smaller than this part of the screen gets a zoom
GLIDE = 150  # changed pixels per frame, of LOOK: the drawn cursor's glide measured 30 to 100, a click's result 429 and up
REACH = 0.7  # seconds the drawn cursor glides before `__demo.click` clicks
LATE = 0.4  # seconds a click can come after a full glide and still be the landing


def mark(out: Path, scene: str, caption: str | None) -> None:
    """Appends `scene` with the time now. `start` marks the start of the recording."""
    entry = {"t": time.time(), "scene": scene, "caption": caption}
    # `start` begins a new recording: marks of an earlier one must not mix in.
    with (out / "marks.jsonl").open("w" if scene == "start" else "a") as marks:
        marks.write(json.dumps(entry) + "\n")
    print(
        f"{scene} at {datetime.fromtimestamp(entry['t']).isoformat(timespec='seconds')}"
    )


def finish(out: Path, video: Path, offset: float | None = None) -> None:
    """Writes 1 frames folder per scene from `video`, the user's screen recording."""
    length = seconds(video)
    raw = out / "frames-raw"
    times = _visible(raw, _extract(video, raw))
    marks = _marks(out)
    start = _start(video, marks, length, offset)
    print(f"{video.name}: {length:.1f} s, {len(times)} frames that change", flush=True)

    gaps = _gaps(times)
    scenes = [m for m in marks if m["scene"] != "start"] or [
        {"scene": "01", "caption": None, "t": start}
    ]
    (out / "scenes.json").write_text(
        json.dumps(list(dict.fromkeys(m["scene"] for m in scenes)))
    )
    cuts = [0.0] + [_snap(m["t"] - start, gaps) for m in scenes[1:]] + [length]
    for entry in scenes:
        retire(out, entry["scene"])
    for index, entry in enumerate(scenes):
        a, b = cuts[index], cuts[index + 1]
        inside = [(n, t) for n, t in times if a <= t < b]
        if not inside:
            print(
                f"{entry['scene']}: no frames between {a:.1f} and {b:.1f} s", flush=True
            )
            continue
        before = [(n, t) for n, t in times if t < a]
        _scene(out, raw, entry, before[-1:] + inside, b, index + 1)


# --- frames ---


def _extract(video: Path, raw: Path) -> list[tuple[str, float]]:
    """Saves each frame that differs from the one before, cropped to 16:9.

    The frames stay in `raw` for the next `finish` of the same video. A new
    video, or the same file filmed again, extracts them again.
    """
    listing = raw / "times.json"
    source = _source(video)
    if listing.exists():
        cached = json.loads(listing.read_text())
        if cached.get("source") == source:
            return [tuple(x) for x in cached["frames"]]
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    # 16:9 from the middle, then 1 size for every recording.
    frames = (
        "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)',"
        f"scale={WIDTH * SHARP}:{HEIGHT * SHARP}:flags=lanczos,fps={SAMPLE},"
        "mpdecimate=hi=768:lo=320:frac=0.1,showinfo"
    )
    printed = log(
        *("-i", str(video), "-an", "-vf", frames),
        *("-fps_mode", "vfr", "-q:v", "3", str(raw / "%06d.jpg")),
    )
    names = sorted(p.name for p in raw.glob("*.jpg"))
    if not names:
        raise SystemExit(f"no frames from {video}:\n{printed[-1500:]}")
    times = list(zip(names, pts(printed)))
    listing.write_text(json.dumps({"source": source, "frames": times}))
    return times


def _source(video: Path) -> dict:
    stat = video.stat()
    return {"path": str(video.resolve()), "size": stat.st_size, "mtime": stat.st_mtime}


def _visible(raw: Path, times: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Drops the frames that change less than a caret blink, so still is still."""
    kept, last = [], None
    for name, at in times:
        small = _small(raw, name)
        if last is None or _changed(small, last).sum() >= CARET:
            kept.append((name, at))
            last = small
    return kept


def _small(raw: Path, name: str) -> np.ndarray:
    image = Image.open(raw / name)
    image.draft("L", LOOK)
    return np.asarray(image.convert("L").resize(LOOK), dtype=np.int16)


def _changed(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.abs(a - b) > DIFF


# --- timing ---


def _marks(out: Path) -> list[dict]:
    path = out / "marks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _start(
    video: Path, marks: list[dict], length: float, offset: float | None
) -> float:
    """The clock time of the video's first frame."""
    if offset is not None:
        return (marks[0]["t"] if marks else 0.0) - offset
    started = next((m["t"] for m in marks if m["scene"] == "start"), None)
    stamp = re.search(
        r"creation_?date\s*:\s*(\S+)|creation_time\s*:\s*(\S+)", log("-i", str(video))
    )
    if stamp:
        # Python 3.10, on the pip path, reads no trailing Z.
        utc = (stamp.group(1) or stamp.group(2)).replace("Z", "+00:00")
        made = datetime.fromisoformat(utc).timestamp()

        # Some recorders stamp the end, not the start: take the one the marks fit.
        def inside(s: float) -> bool:
            return all(s - 2 <= m["t"] <= s + length + 2 for m in marks)

        for guess in [made, made - length]:
            if marks and inside(guess):
                return guess
    if started is not None:
        return started
    return marks[0]["t"] if marks else 0.0


def _gaps(times: list[tuple[str, float]]) -> list[tuple[float, float]]:
    """The still spans: no changed frame for STILL seconds or more."""
    return [(a, b) for (_, a), (_, b) in pairwise(times) if b - a >= STILL]


def _snap(at: float, gaps: list[tuple[float, float]]) -> float:
    """Moves a scene cut to the end of the still gap around its mark.

    The agent stamps a mark, then acts: the scene starts where the screen
    starts to change after the mark, not at a gap that comes later.
    """
    around = [b for a, b in gaps if a - SLACK <= at <= b + SLACK]
    return around[0] - KEEP / 2 if around else at


# --- 1 scene ---


def _scene(
    out: Path,
    raw: Path,
    entry: dict,
    inside: list[tuple[str, float]],
    end: float,
    number: int,
) -> None:
    folder = out / "frames" / entry["scene"]
    folder.mkdir(parents=True)
    frames, bursts, total = _retime(inside, end, narrated(out, entry["scene"]))
    for name, _ in frames:
        try:
            (folder / name).hardlink_to(raw / name)
        except OSError:
            shutil.copy(raw / name, folder / name)
    camera, events, total = _camera(raw, frames, bursts, total)
    Take(
        frames=frames,
        end=total,
        events=events,
        camera=camera,
        fast=[],
        caption=[str(number), entry["caption"]] if entry.get("caption") else None,
        card=False,
        size=[WIDTH, HEIGHT],
        scale=SHARP,
        source="screen",
    ).save(folder / "manifest.json")
    print(
        f"{entry['scene']}: {len(frames)} frames, {total:.1f} s, "
        f"{len(events)} actions, {len(camera)} camera moves",
        flush=True,
    )


def _retime(
    inside: list[tuple[str, float]], end: float, target: float | None
) -> tuple[list[list], list[tuple[int, float]], float]:
    """The frames in video time, the start of each burst of change, and the length.

    Each still gap keeps `keep` seconds, the rest plays as recorded. `inside`
    starts with the last frame of the scene before, when there is one: the
    screen as it was before this scene's first change.
    """
    gaps = len(_gaps(inside))
    keep = KEEP
    if target and gaps:
        # A narration longer than the picture: the pauses grow, so each
        # result stays on screen while the voice speaks about it.
        busy = sum(
            min(b - a, STILL) for (_, a), (_, b) in pairwise(inside) if b - a < STILL
        )
        keep = min(max(KEEP, (target - busy) / (gaps + 1)), LONGEST)
    clock, last, frames, bursts = 0.0, inside[0][1], [], []
    for name, at in inside:
        gap = at - last
        if gap >= STILL:
            bursts.append((len(frames), clock + keep))
        clock += keep if gap >= STILL else gap
        last = at
        frames.append([name, clock])
    return frames, bursts, clock + max(min(end - last, keep), KEEP)


def _landing(raw: Path, frames: list[list], first: int, stop: int) -> int:
    """The frame where the click lands, when the burst starts with a glide.

    With `__demo.click` the drawn cursor moves first and the page changes
    after: the sound and the zoom go to the click, not to the glide. A burst
    without a glide, or one whose click changes too little to see, keeps its
    first frame or the end of a full glide.
    """
    start = frames[first][1]
    last = _small(raw, frames[max(first - 1, 0)][0])
    for index in range(first, stop + 1):
        image = _small(raw, frames[index][0])
        changed = _changed(image, last).sum()
        last = image
        if changed > GLIDE:
            return index if frames[index][1] - start < REACH + LATE else first
        if frames[index][1] - start >= REACH and index > first:
            return index
    return first


def _camera(
    raw: Path, frames: list[list], bursts: list[tuple[int, float]], total: float
) -> tuple[list[Note], list[dict], float]:
    """1 click sound per burst; a zoom on a burst that changes a small area.

    Returns the camera notes, the sounds, and the scene length, which grows
    when the last zoom needs time to hold its result before it goes wide.
    """
    camera, events, zoomed = [], [], False
    for index, (first, _) in enumerate(bursts):
        stop = bursts[index + 1][0] - 1 if index + 1 < len(bursts) else len(frames) - 1
        first = _landing(raw, frames, first, stop)
        at = frames[first][1]
        events.append({"t": at, "kind": "click"})
        before = _small(raw, frames[max(first - 1, 0)][0])
        after = _small(raw, frames[stop][0])
        changed = np.argwhere(_changed(after, before))
        if len(changed) < NOTICED:
            continue
        (y0, x0), (y1, x1) = changed.min(0), changed.max(0)
        area = (x1 - x0) * (y1 - y0) / (LOOK[0] * LOOK[1])
        if area <= SMALL:
            cx = (x0 + x1) / 2 / LOOK[0] * WIDTH
            cy = (y0 + y1) / 2 / LOOK[1] * HEIGHT
            fill = FILL / max(area, TINY) ** 0.5
            cx, cy, zoom = aim(cx, cy, min(ZOOM, max(LEAST, fill)), OUTPUT, SHARP)
            camera.append(Note(max(at - LEAD, 0), cx, cy, zoom, IN))
            zoomed = True
        elif zoomed:
            camera.append(_wide(at))
            zoomed = False
    if zoomed:
        out = max(total - AFTER, camera[-1].t + camera[-1].d + HOLD)
        camera.append(_wide(out))
        total = max(total, out + AFTER)
    return camera, events, total


def _wide(at: float) -> Note:
    return Note(at, WIDTH / 2, HEIGHT / 2, 1.0, OUT)
