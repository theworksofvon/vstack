"""The narration text rules that every voice shares.

In a narration text, `[pause 0.8]` is 0.8 s of silence and an empty line is
0.5 s. `pronounce.json` beside the texts maps a word to how to say it, for
example {"MI": "M I", "Duchess": "Dutchess"}.
"""

import json
import re
from pathlib import Path

PAUSE = re.compile(r"\[pause\s+([\d.]+)\]|\n\s*\n")


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
