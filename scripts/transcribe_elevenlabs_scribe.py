#!/usr/bin/env python3
"""Transcribe local audio or video with ElevenLabs Scribe.

Credentials are read from environment variables only. The script never prints
API keys or the uploaded media payload.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4


DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v2"
DEFAULT_MAX_BYTES = 500 * 1024 * 1024


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def request_error_body(response_body: str) -> str:
    try:
        body = json.loads(response_body)
    except json.JSONDecodeError:
        return response_body[:500]

    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            status = detail.get("status")
            message = detail.get("message")
            if status and message:
                return f"{status}: {message}"
            if message:
                return str(message)
            if status:
                return str(status)
        if isinstance(detail, str):
            return detail

        error = body.get("error")
        if isinstance(error, dict):
            status = error.get("status")
            message = error.get("message")
            if status and message:
                return f"{status}: {message}"
            if message:
                return str(message)
            if status:
                return str(status)
        if isinstance(error, str):
            return error

        for key in ("message", "Message", "Code", "ErrMsg"):
            if body.get(key):
                return str(body[key])

    return json.dumps(body, ensure_ascii=True)[:500]


def multipart_body(fields: dict[str, str], file_path: pathlib.Path) -> tuple[str, bytes]:
    boundary = "video-intel-" + uuid4().hex
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
            str(value).encode("utf-8"),
            b"\r\n",
        ])

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend([
        f"--{boundary}\r\n".encode("ascii"),
        (
            'Content-Disposition: form-data; name="file"; '
            f'filename="{file_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
        file_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ])
    return boundary, b"".join(chunks)


def request_transcript(endpoint: str, api_key: str, fields: dict[str, str], audio: pathlib.Path, timeout: float) -> dict[str, Any]:
    boundary, body = multipart_body(fields, audio)
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs HTTP {exc.code}: {request_error_body(detail)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ElevenLabs request failed: {exc.reason}") from exc


def extract_result(response: dict[str, Any], model: str) -> dict[str, Any]:
    return {
        "provider": "elevenlabs-scribe",
        "model": model,
        "language_code": response.get("language_code"),
        "language_probability": response.get("language_probability"),
        "text": response.get("text", ""),
        "words": response.get("words", []),
        "entities": response.get("entities", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe local audio or video with ElevenLabs Scribe.")
    parser.add_argument("audio", type=pathlib.Path, help="Audio or video file to transcribe")
    parser.add_argument("--endpoint", default=os.getenv("ELEVENLABS_STT_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=os.getenv("ELEVENLABS_STT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--language", default=os.getenv("ELEVENLABS_STT_LANGUAGE_CODE") or os.getenv("VIDEO_INTEL_ASR_LANGUAGE"))
    parser.add_argument(
        "--tag-audio-events",
        action=argparse.BooleanOptionalAction,
        default=env_bool("ELEVENLABS_STT_TAG_AUDIO_EVENTS", True),
    )
    parser.add_argument(
        "--diarize",
        action=argparse.BooleanOptionalAction,
        default=env_bool("ELEVENLABS_STT_DIARIZE", False),
    )
    parser.add_argument(
        "--no-verbatim",
        action=argparse.BooleanOptionalAction,
        default=env_bool("ELEVENLABS_STT_NO_VERBATIM", False),
    )
    parser.add_argument(
        "--timestamps-granularity",
        choices=("none", "word", "character"),
        default=os.getenv("ELEVENLABS_STT_TIMESTAMPS_GRANULARITY", "word"),
    )
    parser.add_argument("--num-speakers", type=int, default=env_optional_int("ELEVENLABS_STT_NUM_SPEAKERS"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("ELEVENLABS_STT_TIMEOUT", "120")))
    parser.add_argument("--max-bytes", type=int, default=int(os.getenv("VIDEO_INTEL_STT_MAX_BYTES", str(DEFAULT_MAX_BYTES))))
    args = parser.parse_args()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit("missing ELEVENLABS_API_KEY")

    audio = args.audio.expanduser().resolve()
    if not audio.is_file():
        raise SystemExit(f"audio file not found: {audio}")

    audio_size = audio.stat().st_size
    if audio_size > args.max_bytes:
        raise SystemExit(
            f"audio file is {audio_size} bytes, above max {args.max_bytes}; "
            "use prepare_video_intel.py's audio-asr.mp3 output or a hosted source/asynchronous STT path"
        )

    fields = {
        "model_id": args.model,
        "tag_audio_events": "true" if args.tag_audio_events else "false",
        "timestamps_granularity": args.timestamps_granularity,
        "diarize": "true" if args.diarize else "false",
        "no_verbatim": "true" if args.no_verbatim else "false",
    }
    if args.language:
        fields["language_code"] = args.language
    if args.num_speakers is not None:
        fields["num_speakers"] = str(args.num_speakers)

    try:
        response = request_transcript(args.endpoint, api_key, fields, audio, args.timeout)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(extract_result(response, args.model), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
