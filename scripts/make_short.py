"""Assemble a vertical Short (1080x1920 mp4) from a script + local TTS.

Pipeline: script lines -> Piper TTS (one WAV per line, so timing is exact,
no estimation) -> concat audio -> animated gradient background ->
burned-in captions, one line at a time -> muxed mp4.

Pure local tooling: ffmpeg + piper. No network calls, no accounts.
"""

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "en_US-lessac-medium.onnx"
WIDTH, HEIGHT = 1080, 1920
SYSTEM_FONT = Path("C:/Windows/Fonts/segoeuib.ttf")
FONT_NAME = "caption-font.ttf"


def run(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def synth_line(text: str, out_wav: Path):
    proc = subprocess.run(
        ["python", "-m", "piper", "-m", str(MODEL), "-f", str(out_wav)],
        input=text,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"piper failed: {proc.stderr}")


def escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def wrap_caption(text: str, max_chars: int = 20) -> str:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def build_short(lines: list[str], work_dir: Path, out_path: Path):
    work_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SYSTEM_FONT, work_dir / FONT_NAME)

    # 1. Synthesize each line separately so caption timing is exact.
    line_wavs = []
    for i, line in enumerate(lines):
        wav_path = work_dir / f"line_{i:02d}.wav"
        synth_line(line, wav_path)
        line_wavs.append(wav_path)

    durations = [wav_duration(w) for w in line_wavs]
    total = sum(durations)

    # 2. Concat the per-line audio into one track.
    concat_list = work_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{w.name}'" for w in line_wavs), encoding="utf-8"
    )
    full_audio = work_dir / "full_audio.wav"
    run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(full_audio)],
        cwd=work_dir,
    )

    # 3. Animated gradient background, exact duration of the audio.
    background = work_dir / "background.mp4"
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"gradients=size={WIDTH}x{HEIGHT}:speed=0.02:duration={total:.3f}:rate=30",
            "-pix_fmt", "yuv420p",
            str(background),
        ]
    )

    # 4. Burn in one drawtext filter per line, timed back-to-back.
    filters = []
    t = 0.0
    for line, dur in zip(lines, durations):
        start, end = t, t + dur
        safe = escape_drawtext(wrap_caption(line))
        filters.append(
            f"drawtext=fontfile={FONT_NAME}:text='{safe}':fontcolor=white:fontsize=64:"
            f"box=1:boxcolor=black@0.45:boxborderw=24:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"line_spacing=12:enable='between(t,{start:.3f},{end:.3f})'"
        )
        t = end
    filter_chain = ",".join(filters)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg", "-y",
            "-i", str(background),
            "-i", str(full_audio),
            "-vf", filter_chain,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            str(out_path),
        ],
        cwd=work_dir,
    )
    return total


if __name__ == "__main__":
    sample_lines = [
        "You don't need a GPU cluster to run your own AI.",
        "An 8 billion parameter model runs fine on a normal desktop.",
        "No API key. No bill. Nothing leaves your machine.",
        "Follow for more self-hosted AI tips.",
    ]
    dur = build_short(sample_lines, ROOT / "work" / "sample", ROOT / "exports" / "pending" / "sample.mp4")
    print(f"Done. Duration: {dur:.1f}s")
