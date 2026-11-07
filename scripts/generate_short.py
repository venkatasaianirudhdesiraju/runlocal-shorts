"""Draft one Short end-to-end: topic backlog -> Ollama script -> local TTS -> mp4.

Writes the finished video to exports/pending/<slug>.mp4 with a metadata.json
(title/description/tags) alongside it. Never uploads anywhere — a human
watches it and uploads manually (or approves the upload step once that's
wired up). Only scripts/topics/metadata are committed to git; video files
stay local (gitignored) since they're large binaries, not something to
diff or review in git.
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_short import ROOT, build_short  # noqa: E402

TOPICS_FILE = ROOT / "data" / "topics.json"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "llama3.1:8b"

SYSTEM_PROMPT = """You write scripts for RunLocal Notes Shorts, a channel about self-hosted AI and \
local-first developer tooling. Write a tight 40-55 second voiceover script as a JSON array of 4-6 \
short strings, each one sentence, meant to be read aloud one at a time. Start with the given hook, \
rephrased if needed to flow naturally as the first line. Keep every line under 100 characters. Be \
concrete and technically accurate — never invent statistics, benchmarks, or product names you are \
not sure exist. End with a short, natural call to action (e.g. follow for more). Respond with ONLY \
the JSON array, nothing else.
"""


def next_topic(topics):
    for t in topics:
        if t["status"] == "pending":
            return t
    return None


def call_ollama(topic) -> list[str]:
    user_prompt = f"Hook: {topic['hook']}\nAngle: {topic['angle']}"
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    raw = data["message"]["content"].strip()
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"Model did not return a JSON array:\n{raw}")
    lines = json.loads(match.group(0))
    return [str(line).strip() for line in lines if str(line).strip()]


def run(cmd):
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    topics = json.loads(TOPICS_FILE.read_text())
    topic = next_topic(topics)
    if topic is None:
        print("No pending topics left in data/topics.json")
        return 0

    print(f"Scripting: {topic['hook']}")
    lines = call_ollama(topic)
    print("\n".join(f"  {i+1}. {l}" for i, l in enumerate(lines)))

    out_path = ROOT / "exports" / "pending" / f"{topic['slug']}.mp4"
    work_dir = ROOT / "work" / topic["slug"]
    duration = build_short(lines, work_dir, out_path)

    metadata = {
        "slug": topic["slug"],
        "title": topic["hook"][:95],
        "description": " ".join(lines) + "\n\n#Shorts #SelfHostedAI #LocalLLM",
        "tags": ["selfhosted", "localllm", "ai", "shorts"],
        "script_lines": lines,
        "duration_seconds": round(duration, 1),
        "privacy_status": "private",
    }
    (out_path.parent / f"{topic['slug']}.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    topic["status"] = "drafted"
    TOPICS_FILE.write_text(json.dumps(topics, indent=2) + "\n")

    run(["git", "add", str(TOPICS_FILE.relative_to(ROOT))])
    run(
        [
            "git",
            "commit",
            "-m",
            f"Mark topic drafted: {topic['hook']}\n\nVideo rendered locally to exports/pending/{topic['slug']}.mp4 (not committed — gitignored binary). Review and upload manually.",
        ]
    )
    run(["git", "push", "origin", "main"])

    print(f"\nDone: {out_path}")
    print("Not uploaded anywhere. Review it, then upload manually (or via the upload step once set up).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
