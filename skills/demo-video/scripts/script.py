"""The narration text rules that every voice shares.

In a narration text, `[pause 0.8]` is 0.8 s of silence and an empty line is
0.5 s. `pronounce.json` beside the texts maps a word to how to say it, for
example {"MI": "M I", "Duchess": "Dutchess"}.
"""

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np
import soundfile as sf

PAUSE = re.compile(r"\[pause\s+([\d.]+)\]|\n\s*\n")


Voice = Callable[[str], Iterable]  # 1 line of text -> its audio, in chunks


def narrate(folder: Path, rate: int, voice: Voice) -> None:
    """Reads each NN.txt of `folder` to NN.wav."""
    said = words(folder)
    for text in sorted(folder.glob("*.txt")):
        audio = render(text.read_text(), said, rate, voice)
        sf.write(text.with_suffix(".wav"), audio, rate)
        print(f"{text.with_suffix('.wav')}  {len(audio) / rate:.1f} s", flush=True)


def render(text: str, said: dict[str, str], rate: int, voice: Voice) -> np.ndarray:
    """The audio of 1 narration text: each line spoken, each pause silent."""
    audio = []
    for part in parts(text, said):
        if isinstance(part, float):
            audio.append(np.zeros(int(rate * part), dtype=np.float32))
        else:
            audio += [np.asarray(chunk, dtype=np.float32) for chunk in voice(part)]
    return np.concatenate(audio)


def words(folder: Path) -> dict[str, str]:
    table = folder / "pronounce.json"
    return json.loads(table.read_text()) if table.exists() else {}


def parts(text: str, said: dict[str, str]) -> list[str | float]:
    """The text as lines to speak and seconds of silence, in order."""
    for word, sound in said.items():
        text = re.sub(rf"\b{re.escape(word)}\b", sound, text)
    found, at = [], 0
    for match in PAUSE.finditer(text):
        found.append(text[at : match.start()].strip())
        found.append(float(match.group(1) or 0.5))
        at = match.end()
    found.append(text[at:].strip())
    return [part for part in found if part != ""]
