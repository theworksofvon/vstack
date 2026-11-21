#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.12.*"
# dependencies = ["mlx-audio", "soundfile", "numpy", "imageio-ffmpeg"]
# ///
"""Narration in the user's own voice: a local clone, on a Mac with Apple silicon.

  clone.py keep <recording> [--text "what it says"]   save the voice sample, 1 time
  clone.py speak <folder>                             each NN.txt -> NN.wav, in that voice

The model is Qwen3-TTS (Apache-2.0) through mlx-audio. It needs no account
and no key; the first run downloads about 2 GB. The sample is 10 to 20 s of
the user who reads PASSAGE aloud, in a quiet room.
"""

import argparse
import shutil
import sys
from pathlib import Path

import soundfile as sf
from script import narrate

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
RATE = 24_000  # the sample rate of the Qwen3-TTS model
HOME = Path.home() / ".config" / "demo-video" / "voice"
PASSAGE = (
    "Hi, this is my voice for the demo videos. I open the app, I click the "
    "button, and the result shows up on the screen. That is all it takes."
)


def keep(recording: Path, text: str) -> None:
    """Saves the sample as 24 kHz mono, without the silence at the ends."""
    HOME.mkdir(parents=True, exist_ok=True)
    from media import ffmpeg, run

    sample = HOME / "sample.wav"
    edge = "silenceremove=start_periods=1:start_threshold=-45dB"
    run(
        [ffmpeg(), "-v", "error", "-y", "-i", str(recording), "-ac", "1", "-ar"]
        + [
            str(RATE),
            "-af",
            f"{edge},areverse,{edge},areverse",
            "-t",
            "20",
            str(sample),
        ]
    )
    (HOME / "sample.txt").write_text(text)
    length = len(sf.read(sample)[0]) / RATE
    if length < 6:
        sys.exit(f"the sample is {length:.1f} s: record 10 to 20 s of speech")
    print(f"voice saved: {sample}, {length:.1f} s")


def speak(folder: Path) -> None:
    sample = HOME / "sample.wav"
    if not sample.exists():
        sys.exit(f"no voice sample: run `demo clone <recording>` first ({sample})")
    from mlx_audio.tts.utils import load_model

    model = load_model(MODEL)
    heard = (HOME / "sample.txt").read_text()

    def say(line: str):
        found = model.generate(
            text=line, ref_audio=str(sample), ref_text=heard, lang_code="en"
        )
        return (result.audio for result in found)

    narrate(folder, model.sample_rate, say)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["keep", "speak"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--text", default=PASSAGE, help="the words in the recording")
    args = parser.parse_args()
    if args.command == "keep":
        keep(args.path, args.text)
    else:
        speak(args.path)


if __name__ == "__main__":
    if shutil.which("sw_vers") is None:
        sys.exit("the voice clone runs on a Mac with Apple silicon only")
    main()
