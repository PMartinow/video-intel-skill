#!/usr/bin/env python3
"""Transcribe local audio with Alibaba Cloud Model Studio Qwen-ASR.

Credentials are read from environment variables only. The script never prints
API keys or the encoded audio payload.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-asr-flash"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def audio_data_url(path: pathlib.Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def request_json(url: str, api_key: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DashScope request failed: {exc.reason}") from exc


def extract_result(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    message = choices[0].get("message", {}) if choices else {}
    return {
        "provider": "dashscope-qwen-asr",
        "model": response.get("model"),
        "text": message.get("content", ""),
        "annotations": message.get("annotations", []),
        "usage": response.get("usage"),
        "id": response.get("id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe local audio with DashScope Qwen-ASR.")
    parser.add_argument("audio", type=pathlib.Path, help="Audio file to transcribe")
    parser.add_argument("--base-url", default=os.getenv("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.getenv("DASHSCOPE_ASR_MODEL", DEFAULT_MODEL))
    parser.add_argument("--language", default=os.getenv("VIDEO_INTEL_ASR_LANGUAGE"))
    parser.add_argument("--enable-itn", action="store_true", default=env_bool("VIDEO_INTEL_ASR_ENABLE_ITN", False))
    parser.add_argument("--context", default=os.getenv("VIDEO_INTEL_ASR_CONTEXT"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("VIDEO_INTEL_ASR_TIMEOUT", "120")))
    parser.add_argument("--max-bytes", type=int, default=int(os.getenv("VIDEO_INTEL_ASR_MAX_BYTES", str(DEFAULT_MAX_BYTES))))
    args = parser.parse_args()

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIBABA_API_KEY")
    if not api_key:
        raise SystemExit("missing DASHSCOPE_API_KEY or ALIBABA_API_KEY")

    audio = args.audio.expanduser().resolve()
    if not audio.is_file():
        raise SystemExit(f"audio file not found: {audio}")

    audio_size = audio.stat().st_size
    if audio_size > args.max_bytes:
        raise SystemExit(
            f"audio file is {audio_size} bytes, above max {args.max_bytes}; "
            "use prepare_video_intel.py's audio-asr.mp3 output or a public URL/asynchronous ASR path"
        )

    asr_options: dict[str, Any] = {"enable_itn": args.enable_itn}
    if args.language:
        asr_options["language"] = args.language

    messages: list[dict[str, Any]] = []
    if args.context:
        messages.append({"role": "system", "content": [{"text": args.context}]})
    messages.append({
        "role": "user",
        "content": [{"type": "input_audio", "input_audio": {"data": audio_data_url(audio)}}],
    })

    endpoint = args.base_url.rstrip("/") + "/chat/completions"
    try:
        response = request_json(
            endpoint,
            api_key,
            {
                "model": args.model,
                "messages": messages,
                "stream": False,
                "asr_options": asr_options,
            },
            args.timeout,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(extract_result(response), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
