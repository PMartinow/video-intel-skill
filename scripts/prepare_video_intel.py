#!/usr/bin/env python3
"""Prepare a video for transcript + frame analysis.

Outputs JSON with a temp work directory, extracted canonical WAV audio, sampled
frame paths, and basic ffprobe metadata. The script intentionally does not
perform transcription or analysis.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"missing required tool: {name}")
    return path


def ffprobe(video: pathlib.Path) -> dict[str, Any]:
    proc = run([
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video),
    ])
    return json.loads(proc.stdout)


def duration_seconds(meta: dict[str, Any]) -> float:
    fmt = meta.get("format", {})
    try:
        return float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def pick_times(duration: float, count: int) -> list[float]:
    if count <= 0 or duration <= 0:
        return []
    if duration < 1:
        return [0.0]
    usable_count = max(1, count)
    start = min(0.5, duration * 0.05)
    end = max(start, duration - min(0.5, duration * 0.05))
    if usable_count == 1:
        return [duration / 2]
    step = (end - start) / (usable_count - 1)
    return [start + i * step for i in range(usable_count)]


def extract_audio(video: pathlib.Path, audio_path: pathlib.Path) -> bool:
    proc = subprocess.run([
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vn",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 44


def extract_asr_mp3(video: pathlib.Path, audio_path: pathlib.Path, bitrate: str) -> bool:
    proc = subprocess.run([
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        bitrate,
        str(audio_path),
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 0


def extract_frame(video: pathlib.Path, timestamp: float, frame_path: pathlib.Path) -> bool:
    proc = subprocess.run([
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(frame_path),
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0 and frame_path.exists() and frame_path.stat().st_size > 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract canonical audio and sampled frames for video-intel.")
    parser.add_argument("video", type=pathlib.Path, help="Path to the input video")
    parser.add_argument("--frames", type=int, default=12, help="Number of representative frames to sample")
    parser.add_argument("--workdir", type=pathlib.Path, default=None, help="Optional output work directory")
    parser.add_argument(
        "--asr-mp3-bitrate",
        default="32k",
        help="Bitrate for compact MP3 used by cloud ASR helpers; set empty to skip",
    )
    args = parser.parse_args()

    require_tool("ffmpeg")
    require_tool("ffprobe")

    video = args.video.expanduser().resolve()
    if not video.exists() or not video.is_file():
        raise SystemExit(f"video file not found: {video}")

    meta = ffprobe(video)
    duration = duration_seconds(meta)
    workdir = args.workdir or pathlib.Path(tempfile.mkdtemp(prefix="video-intel-"))
    workdir.mkdir(parents=True, exist_ok=True)
    frames_dir = workdir / "frames"
    frames_dir.mkdir(exist_ok=True)

    audio_path = workdir / "audio.wav"
    audio_ok = extract_audio(video, audio_path)
    asr_audio_path = workdir / "audio-asr.mp3"
    asr_audio_ok = False
    if args.asr_mp3_bitrate:
        asr_audio_ok = extract_asr_mp3(video, asr_audio_path, args.asr_mp3_bitrate)

    frames: list[dict[str, Any]] = []
    for idx, timestamp in enumerate(pick_times(duration, args.frames), start=1):
        frame_path = frames_dir / f"frame-{idx:03d}-{round(timestamp * 1000):06d}ms.jpg"
        if extract_frame(video, timestamp, frame_path):
            frames.append({"index": idx, "timestamp_seconds": round(timestamp, 3), "path": str(frame_path)})

    output = {
        "video": str(video),
        "workdir": str(workdir),
        "duration_seconds": round(duration, 3) if duration else None,
        "audio": {"ok": audio_ok, "path": str(audio_path) if audio_ok else None},
        "asr_audio": {
            "ok": asr_audio_ok,
            "path": str(asr_audio_path) if asr_audio_ok else None,
            "bitrate": args.asr_mp3_bitrate if asr_audio_ok else None,
        },
        "frames": frames,
        "streams": [
            {
                "index": s.get("index"),
                "codec_type": s.get("codec_type"),
                "codec_name": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "duration": s.get("duration"),
            }
            for s in meta.get("streams", [])
        ],
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
