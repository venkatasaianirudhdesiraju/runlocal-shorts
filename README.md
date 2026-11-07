# RunLocal Shorts

Local pipeline for drafting YouTube Shorts about self-hosted AI / local-first dev tooling —
same niche as [runlocal-notes](https://github.com/venkatasaianirudhdesiraju/runlocal-notes).

Nothing here touches the network except pulling topics from `data/topics.json` and pushing
script/metadata changes to this repo. Script generation runs on a local Ollama model
(`llama3.1:8b`), voiceover on local Piper TTS, and video assembly on ffmpeg. No cloud API,
no account required to generate a draft.

## What it does *not* do

It does not upload anything to YouTube. `exports/pending/*.mp4` are finished, reviewable
videos sitting on disk — gitignored, since they're large binaries git shouldn't track. You
watch them, and upload manually via YouTube Studio (or the upload step, once wired up, which
will only ever upload as **private** so you still do the actual publish click yourself).

## Setup

```bash
pip install -r requirements.txt
winget install --id Gyan.FFmpeg -e   # if ffmpeg isn't already installed
```

Piper needs a voice model — already downloaded to `models/en_US-lessac-medium.onnx` (not
committed, ~60MB). Re-download if missing:

```bash
curl -L -o models/en_US-lessac-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -L -o models/en_US-lessac-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

## Run

```bash
python scripts/generate_short.py
```

Picks the next `pending` topic from `data/topics.json`, writes a script with Ollama, renders
`exports/pending/<slug>.mp4` + `<slug>.json` (title/description/tags), marks the topic
`drafted`, and pushes that topics.json update to this repo.

Runs automatically once a day via the `RunLocalShorts-DailyDraft` Windows Scheduled Task
(only while the desktop is on and Ollama is running).

## Publishing

1. Watch the video in `exports/pending/`.
2. Fix anything wrong, or discard it.
3. Upload manually via [YouTube Studio](https://studio.youtube.com), using the title/description
   from the matching `.json` file. Tag `#Shorts` in the title or description.

## Adding more topics

Append entries to `data/topics.json` with a `slug`, `hook`, `angle`, and `status: "pending"`.
