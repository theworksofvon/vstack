"""The build: joins the recorded scenes and their narration into final.mp4.

Per scene: the frames become a 30 fps clip, the camera notes become a crop
that moves, the caption is drawn on top, and the click and key sounds are
mixed under the narration.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from check import sound as _sound
from edit import narration
from media import concat, ffmpeg, seconds, takes, untaken
from PIL import Image, ImageDraw, ImageFont

FPS = 30
RATE = 48_000
LEAD = 0.3  # silence before the narration of a scene
TAIL = 0.5  # the least picture after the narration ends
LOUDNESS = -18  # LUFS: the level of the narrated demos in REFERENCE.md
MUSIC = 0.16  # the music level under the voice, as a part of full level: a first guess
FONTS = [
    ("/System/Library/Fonts/Helvetica.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
]


def sound_level(video: Path) -> float | None:
    return _sound(video)[0]


def run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(cmd[:8])} ...\n{done.stderr[-2500:]}")


def font(size: int):
    for path, index in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    return ImageFont.load_default(size)


# --- camera ---


# The camera is a spring: it starts slowly, arrives with a soft tail, and when a
# new target comes mid-move it bends towards it with no jerk. A spring is linear,
# so its path through many targets is the sum of 1 step response per change.
SETTLE = 5.0  # stiffness x seconds: the spring is 96% of the way after a note's `d`
BOUNCE = 0.8  # damping of a zoom-in: below 1 it passes the target by 1.5%, then returns


def spring(at: float, length: float, change: float, damping: float) -> str:
    """An ffmpeg term: the move of a spring that starts at `at` towards `change`."""
    w = SETTLE / max(length, 0.05)
    t = f"st(0,max(it-{at:.3f},0))"
    if damping >= 1:
        return f"{change:.4f}*({t}*0+1-(1+{w:.4f}*ld(0))*exp(-{w:.4f}*ld(0)))"
    wd = w * (1 - damping**2) ** 0.5
    ratio = damping / (1 - damping**2) ** 0.5
    return (
        f"{change:.4f}*({t}*0+1-exp(-{damping * w:.4f}*ld(0))"
        f"*(cos({wd:.4f}*ld(0))+{ratio:.4f}*sin({wd:.4f}*ld(0))))"
    )


def eased(
    start: float, moves: list[tuple[float, float, float]], bounce: bool = False
) -> str:
    """An ffmpeg expression: `start`, plus 1 spring per (time, seconds, change)."""
    terms = [f"{start:.3f}"]
    for at, length, change in moves:
        if abs(change) < 1e-6:
            continue
        damping = BOUNCE if bounce and change > 0 else 1.0
        terms.append(spring(at, length, change, damping))
    return "+".join(terms)


def camera_filter(manifest: dict) -> str:
    keys = manifest.get("camera") or []
    if not keys:
        return "scale=1920:1080:flags=lanczos"
    width, height = manifest["size"]
    scale = manifest.get("scale", 2)  # device pixels per page pixel
    at = {"cx": width / 2, "cy": height / 2, "z": 1.0}
    moves: dict[str, list[tuple[float, float, float]]] = {"cx": [], "cy": [], "z": []}
    for key in keys:
        for name in moves:
            moves[name].append((key["t"], key["d"], key[name] - at[name]))
            at[name] = key[name]
    zoom = f"max(1,{eased(1.0, moves['z'], bounce=True)})"
    cx = eased(width / 2 * scale, [(t, d, c * scale) for t, d, c in moves["cx"]])
    cy = eased(height / 2 * scale, [(t, d, c * scale) for t, d, c in moves["cy"]])
    return (
        f"zoompan=z='{zoom}':x='clip(({cx})-iw/zoom/2,0,iw-iw/zoom)'"
        f":y='clip(({cy})-ih/zoom/2,0,ih-ih/zoom)':d=1:s=1920x1080:fps={FPS}"
    )


# --- caption ---


def caption_image(path: Path, step: str, text: str) -> Path:
    big, small = font(30), font(22)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    text_w = probe.textlength(text, font=big)
    step_w = probe.textlength(step, font=small)
    badge_w, height, pad = int(step_w + 36), 72, 16
    width = int(pad + badge_w + 22 + text_w + 36)
    image = Image.new("RGBA", (width + 40, height + 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((22, 26, width + 18, height + 22), 36, fill=(0, 0, 0, 70))
    draw.rounded_rectangle(
        (20, 20, width + 20, height + 20), 36, fill=(11, 18, 32, 242)
    )
    draw.rounded_rectangle(
        (20 + pad, 20 + 14, 20 + pad + badge_w, 20 + height - 14),
        22,
        fill=(245, 179, 1, 255),
    )
    draw.text(
        (20 + pad + 18, 20 + height / 2),
        step,
        font=small,
        fill=(26, 19, 0, 255),
        anchor="lm",
    )
    draw.text(
        (20 + pad + badge_w + 22, 20 + height / 2),
        text,
        font=big,
        fill=(255, 255, 255, 255),
        anchor="lm",
    )
    image.save(path)
    return path


# --- sound ---


def tick(rng, pitch: float, length: float, level: float) -> np.ndarray:
    t = np.arange(int(RATE * length)) / RATE
    tone = np.sin(2 * np.pi * pitch * t) * np.exp(-t / (length / 5))
    noise = rng.standard_normal(len(t)) * np.exp(-t / 0.0012)
    return level * (0.75 * tone + 0.5 * noise)


def sound_track(path: Path, seed: int, events: list[dict], total: float) -> Path:
    rng = np.random.default_rng(seed)
    track = np.zeros(int(RATE * (total + 1)))

    def place(at: float, sample: np.ndarray) -> None:
        start = int(RATE * at)
        if start < 0 or start >= len(track):
            return
        end = min(len(track), start + len(sample))
        track[start:end] += sample[: end - start]

    for event in events:
        at = event["t"]
        if event["kind"] == "click":
            place(at, tick(rng, 2300, 0.03, 0.42))
            place(at + 0.075, tick(rng, 3100, 0.022, 0.26))
        elif event["kind"] == "key":
            place(at, tick(rng, rng.uniform(1500, 2100), 0.02, rng.uniform(0.09, 0.14)))
    sf.write(path, np.clip(track[: int(RATE * total)], -1, 1), RATE)
    return path


# --- scenes ---


def load(folder: Path) -> dict:
    cut = folder / "cut.json"
    return json.loads((cut if cut.exists() else folder / "manifest.json").read_text())


def segment(out: Path, scene: str, after_card: bool, before_card: bool) -> Path:
    frames, parts = out / "frames" / scene, out / "segments"
    manifest = load(frames)
    times = [t for _, t in manifest["frames"]]
    lines = []
    for index, (name, at) in enumerate(manifest["frames"]):
        until = times[index + 1] if index + 1 < len(times) else manifest["end"]
        lines.append(concat(frames / name) + f"duration {max(until - at, 0.001):.4f}\n")
    lines.append(concat(frames / manifest["frames"][-1][0]))
    listing = frames / "list.txt"
    listing.write_text("".join(lines))

    picture = manifest["end"] - times[0]
    voice = narration(out, scene)
    spoken = seconds(voice) if voice else 0.0
    total = max(picture, LEAD + spoken + TAIL) if voice else picture
    if not voice:
        voice = parts / f"{scene}.silent.wav"
        sf.write(voice, np.zeros(RATE // 10), RATE)
    sfx = sound_track(
        parts / f"{scene}.sfx.wav",
        len(scene) + sum(map(ord, scene)),
        manifest.get("events") or [],
        total,
    )

    video = f"[0:v]fps={FPS},{camera_filter(manifest)},tpad=stop_mode=clone:stop_duration={max(total - picture, 0) + 0.5:.3f}"
    inputs = [
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-i",
        str(voice),
        "-i",
        str(sfx),
    ]
    is_card = bool(manifest.get("card"))
    # Scene to scene is a straight cut: a dip to black between 2 bright pages is a flash.
    edges = (",fade=t=in:st=0:d=0.5" if is_card or after_card else "") + (
        f",fade=t=out:st={total - 0.5:.3f}:d=0.5" if is_card or before_card else ""
    )
    if manifest.get("caption") and not is_card:
        image = caption_image(parts / f"{scene}.caption.png", *manifest["caption"])
        inputs += ["-loop", "1", "-i", str(image)]
        video += (
            f"{edges}[base];"
            "[3:v]format=rgba,fade=t=in:st=0.4:d=0.4:alpha=1,fade=t=out:st=3.4:d=0.4:alpha=1[cap];"
            "[base][cap]overlay=x=(W-w)/2:y=H-h-18:shortest=0[v]"
        )
    else:
        video += f"{edges}[v]"
    sound = (
        f"[1:a]aresample={RATE},adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={total:.3f}[voice];"
        "[voice][2:a]amix=inputs=2:normalize=0:duration=first[a]"
    )
    path = parts / f"{scene}.mp4"
    run(
        [
            ffmpeg(),
            "-y",
            *inputs,
            "-filter_complex",
            f"{video};{sound}",
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]
        + ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "17"]
        + ["-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k"]
        + ["-ar", str(RATE), "-ac", "2", str(path)]
    )
    print(
        f"{scene}: picture {picture:.1f} s, narration {spoken:.1f} s, segment {total:.1f} s, "
        f"{len(manifest.get('events') or [])} sounds, {len(manifest.get('camera') or [])} camera moves",
        flush=True,
    )
    return path


def master(out: Path, joined: Path, final: Path) -> None:
    """Puts the music file of the folder, when it has one, under the voice; then sets the loudness."""
    music = next(
        (
            p
            for p in sorted(out.glob("music.*"))
            if p.suffix in {".mp3", ".wav", ".m4a"}
        ),
        None,
    )
    encode = [
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        str(RATE),
        "-ac",
        "2",
    ]
    if music:
        length = seconds(joined)
        # The voice pushes the music down while it speaks; the music fades out at the end.
        sound = (
            f"[1:a]aresample={RATE},volume={MUSIC},afade=t=in:d=1.5,"
            f"afade=t=out:st={length - 2:.2f}:d=2[bed];"
            "[0:a]asplit[voice][key];"
            "[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[low];"
            "[voice][low]amix=inputs=2:normalize=0:duration=first[a]"
        )
        mixed = joined.with_name("mixed.mp4")
        run(
            [ffmpeg(), "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(music)]
            + ["-filter_complex", sound, "-map", "0:v", "-map", "[a]", *encode]
            + ["-t", f"{length:.3f}", str(mixed)]
        )
        joined = mixed
    # Measure, then 1 fixed gain: a short clip with long pauses misleads a 1-pass leveller.
    measured = sound_level(joined)
    gain = 0.0 if measured is None else LOUDNESS - measured
    run(
        [
            ffmpeg(),
            "-y",
            "-i",
            str(joined),
            "-af",
            f"volume={gain:.2f}dB,alimiter=limit=0.89",
        ]
        + [*encode, "-movflags", "+faststart", str(final)]
    )


def build(out: Path, names: list[str] | None) -> Path:
    (out / "segments").mkdir(exist_ok=True)
    every = takes(out)
    missing = untaken(out)
    if missing:
        print(f"no take of {missing}: this build is a preview", flush=True)
    scenes = names or every
    cards = {name for name in scenes if load(out / "frames" / name).get("card")}
    parts = [
        segment(
            out,
            scene,
            after_card=index > 0 and scenes[index - 1] in cards,
            before_card=index + 1 < len(scenes) and scenes[index + 1] in cards,
        )
        for index, scene in enumerate(scenes)
    ]
    listing = out / "segments" / "list.txt"
    listing.write_text("".join(concat(part) for part in parts))
    final = out / ("final.mp4" if scenes == every and not missing else "preview.mp4")
    if final.name == "preview.mp4":
        # `check` reads final.mp4: an older one must not pass for this build.
        (out / "final.mp4").unlink(missing_ok=True)
    joined = out / "segments" / "joined.mp4"
    run(
        [ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
        + ["-c", "copy", str(joined)]
    )
    master(out, joined, final)
    print(final, f"{seconds(final):.1f} s", flush=True)
    return final
