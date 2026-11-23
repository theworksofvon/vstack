import numpy as np
import soundfile as sf
from script import narrate

RATE = 1000


def beep(line: str):
    """A stand-in voice: 1 sample per letter, in 2 chunks."""
    half = len(line) // 2
    return [np.ones(half), np.ones(len(line) - half)]


def test_each_text_becomes_a_wav_with_its_pauses(tmp_path):
    (tmp_path / "01.txt").write_text("Click it.\n\nDone. [pause 1.2] MI")
    (tmp_path / "pronounce.json").write_text('{"MI": "M I"}')

    narrate(tmp_path, RATE, beep)

    audio, rate = sf.read(tmp_path / "01.wav")
    spoken = len("Click it.") + len("Done.") + len("M I")
    assert rate == RATE
    assert len(audio) == spoken + int(RATE * 0.5) + int(RATE * 1.2)
