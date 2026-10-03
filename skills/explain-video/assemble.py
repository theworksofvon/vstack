#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Pair each rendered Manim scene with its narration and join them into final.mp4.

Usage: assemble.py <slug-dir>

Expects <slug-dir>/narration/NN.<ext> audio files and Manim's output under
<slug-dir>/media/videos/scenes/*/SNN.mp4. The shorter of each pair is padded
(last frame held, or silence appended) so narration and picture end together.
Needs ffmpeg and ffprobe on PATH.
"""
import subprocess
import sys
from pathlib import Path


def main(root: Path) -> None:
    narration = sorted(p for p in (root / "narration").iterdir() if p.suffix in {".aiff", ".wav", ".mp3", ".m4a"})
    if not narration:
        sys.exit(f"no narration files under {root / 'narration'}")
    segments_dir = root / "segments"
    segments_dir.mkdir(exist_ok=True)
    segments = []
    for audio in narration:
        number = audio.stem
        video = find_scene(root, number)
        segment = segments_dir / f"{number}.mp4"
        pair(video, audio, segment)
        segments.append(segment)
    concat_list = segments_dir / "list.txt"
    concat_list.write_text("".join(f"file '{s.resolve()}'\n" for s in segments))
    out = root / "final.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(out)])
    print(out)


def find_scene(root: Path, number: str) -> Path:
    matches = list((root / "media" / "videos").rglob(f"S{number}.mp4"))
    if not matches:
        sys.exit(f"no rendered scene S{number}.mp4 under {root / 'media' / 'videos'}; render it with manim first")
    return matches[0]


def pair(video: Path, audio: Path, out: Path) -> None:
    dv, da = duration(video), duration(audio)
    target = max(dv, da) + 0.4
    run([
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
        "-filter_complex",
        f"[0:v]tpad=stop_mode=clone:stop_duration={target - dv:.3f}[v];"
        f"[1:a]apad=pad_dur={target - da:.3f}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-ar", "48000",
        str(out),
    ])


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
