#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.12.*"
# dependencies = ["kokoro>=0.9", "soundfile", "numpy"]
# ///
"""Read narration text to audio with Kokoro, a local voice model.

  speak.py <folder> --voice V --speed N     each NN.txt -> NN.wav
  speak.py --samples <folder> --text "..."  1 file per voice, to compare them

In a narration text, `[pause 0.8]` is 0.8 s of silence and an empty line is
0.5 s. `<folder>/pronounce.json` maps a word to how to say it, for example
{"MI": "M I", "Duchess": "Dutchess"}.
"""

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline
from script import parts, words

RATE = 24_000

# name: (who, character). The first letter is the accent, the second the sex.
VOICES = {
    "af_heart": ("American woman", "warm, the default"),
    "af_bella": ("American woman", "bright, more energy"),
    "af_nicole": ("American woman", "soft, close to a whisper"),
    "af_sarah": ("American woman", "even, neutral"),
    "am_michael": ("American man", "even, neutral"),
    "am_fenrir": ("American man", "deep, firm"),
    "am_puck": ("American man", "light, quick"),
    "am_adam": ("American man", "low, plain"),
    "bf_emma": ("British woman", "clear, formal"),
    "bf_isabella": ("British woman", "soft"),
    "bm_george": ("British man", "mature, formal"),
    "bm_fable": ("British man", "storyteller"),
}

_pipes: dict[str, KPipeline] = {}


def pipe(voice: str) -> KPipeline:
    code = voice[0]  # a: American English, b: British English
    if code not in _pipes:
        _pipes[code] = KPipeline(lang_code=code)
    return _pipes[code]


def speak(text: str, voice: str, speed: float, said: dict[str, str]) -> np.ndarray:
    audio = []
    for part in parts(text, said):
        if isinstance(part, float):
            audio.append(np.zeros(int(RATE * part), dtype=np.float32))
        else:
            audio += [a for _, _, a in pipe(voice)(part, voice=voice, speed=speed)]
    return np.concatenate([np.asarray(a, dtype=np.float32) for a in audio])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--samples", action="store_true")
    parser.add_argument(
        "--text",
        default="This is how I sound when I show you the product. Each step takes a few seconds.",
    )
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    if args.samples:
        for voice, (who, character) in VOICES.items():
            path = args.folder / f"{voice}.wav"
            sf.write(path, speak(args.text, voice, args.speed, {}), RATE)
            print(f"{path}  {who}, {character}")
        return
    said = words(args.folder)
    for text in sorted(args.folder.glob("*.txt")):
        audio = speak(text.read_text(), args.voice, args.speed, said)
        sf.write(text.with_suffix(".wav"), audio, RATE)
        print(f"{text.with_suffix('.wav')}  {len(audio) / RATE:.1f} s")


if __name__ == "__main__":
    main()
