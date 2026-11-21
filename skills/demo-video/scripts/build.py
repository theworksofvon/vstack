"""The build: joins the recorded scenes and their narration into final.mp4.

Per scene: the frames become a 30 fps clip, the camera notes become a crop
that moves, the caption is drawn on top, and the click and key sounds are
mixed under the narration.
"""

from pathlib import Path

import camera
import numpy as np
import soundfile as sf
from media import LOUDNESS, concat, ffmpeg, run, seconds, sound
from PIL import Image, ImageDraw, ImageFont
from work import Take, manifest, narration, takes, untaken

FPS = 30
RATE = 48_000
LEAD = 0.3  # silence before the narration of a scene
TAIL = 0.5  # the least picture after the narration ends
FADE = 0.5  # seconds of the fade into and out of a title card
PAD = 0.5  # seconds of held last frame past the segment's end, cut off by -t
SHORTEST = 0.001  # seconds: ffmpeg shows a frame with no duration not at all
MUSIC = 0.16  # the music level under the voice, as a part of full level: a first guess
FONTS = [
    ("/System/Library/Fonts/Helvetica.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
]


def font(size: int):
    for path, index in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    return ImageFont.load_default(size)


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


def segment(out: Path, scene: str, after_card: bool, before_card: bool) -> Path:
    frames, parts = out / "frames" / scene, out / "segments"
    take = manifest(frames)
    picture = take.end - take.frames[0][1]
    voice = narration(out, scene)
    spoken = seconds(voice) if voice else 0.0
    total = max(picture, LEAD + spoken + TAIL) if voice else picture
    if not voice:
        voice = parts / f"{scene}.silent.wav"
        sf.write(voice, np.zeros(RATE // 10), RATE)
    seed = len(scene) + sum(map(ord, scene))
    sfx = sound_track(parts / f"{scene}.sfx.wav", seed, take.events, total)
    inputs = ["-f", "concat", "-safe", "0", "-i", str(_listing(frames, take))]
    inputs += ["-i", str(voice), "-i", str(sfx)]
    caption = bool(take.caption) and not take.card
    if caption:
        image = caption_image(parts / f"{scene}.caption.png", *take.caption)
        inputs += ["-loop", "1", "-i", str(image)]
    fades = (take.card or after_card, take.card or before_card)
    path = parts / f"{scene}.mp4"
    run(
        [ffmpeg(), "-y", *inputs]
        + ["-filter_complex", _filters(take, picture, total, fades, caption)]
        + ["-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}"]
        + ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p"]
        + ["-r", str(FPS), "-c:a", "aac", "-b:a", "160k"]
        + ["-ar", str(RATE), "-ac", "2", str(path)]
    )
    print(
        f"{scene}: picture {picture:.1f} s, narration {spoken:.1f} s, segment {total:.1f} s, "
        f"{len(take.events)} sounds, {len(take.camera)} camera moves",
        flush=True,
    )
    return path


def _listing(frames: Path, take: Take) -> Path:
    """The ffmpeg concat list that shows each frame until the next one."""
    ends = [t for _, t in take.frames[1:]] + [take.end]
    lines = [
        concat(frames / name) + f"duration {max(until - at, SHORTEST):.4f}\n"
        for (name, at), until in zip(take.frames, ends, strict=True)
    ]
    # The concat demuxer drops the last duration unless the last file repeats.
    lines.append(concat(frames / take.frames[-1][0]))
    listing = frames / "list.txt"
    listing.write_text("".join(lines))
    return listing


def _filters(
    take: Take,
    picture: float,
    total: float,
    fades: tuple[bool, bool],
    caption: bool,
) -> str:
    """The picture: camera, held last frame, fades and caption; the sound: voice over clicks."""
    crop = camera.crop(take.camera, take.size, take.scale, FPS)
    held = max(total - picture, 0) + PAD
    video = f"[0:v]fps={FPS},{crop},tpad=stop_mode=clone:stop_duration={held:.3f}"
    # Scene to scene is a straight cut: a dip to black between 2 bright pages is a flash.
    if fades[0]:
        video += f",fade=t=in:st=0:d={FADE}"
    if fades[1]:
        video += f",fade=t=out:st={total - FADE:.3f}:d={FADE}"
    if caption:
        video += (
            "[base];"
            "[3:v]format=rgba,fade=t=in:st=0.4:d=0.4:alpha=1,fade=t=out:st=3.4:d=0.4:alpha=1[cap];"
            "[base][cap]overlay=x=(W-w)/2:y=H-h-18:shortest=0[v]"
        )
    else:
        video += "[v]"
    audio = (
        f"[1:a]aresample={RATE},adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={total:.3f}[voice];"
        "[voice][2:a]amix=inputs=2:normalize=0:duration=first[a]"
    )
    return f"{video};{audio}"


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
        mix = (
            f"[1:a]aresample={RATE},volume={MUSIC},afade=t=in:d=1.5,"
            f"afade=t=out:st={length - 2:.2f}:d=2[bed];"
            "[0:a]asplit[voice][key];"
            "[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[low];"
            "[voice][low]amix=inputs=2:normalize=0:duration=first[a]"
        )
        mixed = joined.with_name("mixed.mp4")
        run(
            [ffmpeg(), "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(music)]
            + ["-filter_complex", mix, "-map", "0:v", "-map", "[a]", *encode]
            + ["-t", f"{length:.3f}", str(mixed)]
        )
        joined = mixed
    # Measure, then 1 fixed gain: a short clip with long pauses misleads a 1-pass leveller.
    measured = sound(joined)[0]
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
    cards = {name for name in scenes if manifest(out / "frames" / name).card}
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
