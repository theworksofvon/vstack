# Narration

Produce one audio file per scene at `narration/NN.<ext>`, numbered to match
the scene classes `SNN` in `scenes.py`. Try the tiers in order and use the
first one whose tool is present. Say which tier was used when you deliver.

## Tier 1: macOS `say`

Present on every Mac, no setup, flat delivery. Good enough to prove the
pipeline and often good enough to keep.

```bash
say -v Samantha -r 175 -o narration/01.aiff -f narration/01.txt
```

`say -v '?'` lists voices; the premium and enhanced ones installed through
System Settings sound markedly better and use the same command.

## Tier 2: Kokoro, local open-weight voice

Near-commercial quality, runs on the CPU, about 300 MB of weights fetched
on first use. Needs `espeak-ng` on PATH for phonemes (Homebrew has it).

```bash
uv run --python 3.12 --with 'kokoro>=0.9' --with soundfile python - <<'PY'
from kokoro import KPipeline
import soundfile as sf, numpy as np, pathlib
pipe = KPipeline(lang_code="a")
for txt in sorted(pathlib.Path("narration").glob("*.txt")):
    chunks = [a for _, _, a in pipe(txt.read_text(), voice="af_heart")]
    sf.write(txt.with_suffix(".wav"), np.concatenate(chunks), 24000)
PY
```

## Tier 3: ElevenLabs

Paid, best quality. Needs `ELEVENLABS_API_KEY` in the environment.

```bash
for f in narration/*.txt; do
  curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb" \
    -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
    -d "{\"text\": $(jq -Rs . < "$f"), \"model_id\": \"eleven_multilingual_v2\"}" \
    -o "${f%.txt}.mp3"
done
```

Only tier 1 has been run end to end in this repo. Tiers 2 and 3 are the
documented command shapes; expect to adjust them the first time.
