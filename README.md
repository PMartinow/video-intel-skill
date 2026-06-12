# Video Intel Skill

Analyze local videos by combining speech transcription with sampled visual
frames. The skill prepares audio and frames with `ffmpeg`, transcribes speech
through a configured STT backend, visually inspects representative frames, and
summarizes what the video says and shows.

## Contents

- `SKILL.md` - Codex skill instructions.
- `scripts/prepare_video_intel.py` - extracts canonical WAV audio, compact MP3
  audio for cloud ASR, and representative frames.
- `scripts/transcribe_elevenlabs_scribe.py` - transcribes local audio or video
  using the ElevenLabs Speech to Text endpoint.
- `scripts/transcribe_dashscope_qwen_asr.py` - transcribes local audio using
  Alibaba Cloud Model Studio Qwen-ASR through the OpenAI-compatible endpoint.
- `agents/openai.yaml` - simple marketplace/agent metadata.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe`
- Optional: ElevenLabs API key for Scribe STT
- Optional: Alibaba Cloud Model Studio / DashScope API key for Qwen-ASR

## ElevenLabs Scribe

Set credentials in your shell, never in the repo:

```bash
read -rsp "ELEVENLABS_API_KEY: " ELEVENLABS_API_KEY; export ELEVENLABS_API_KEY; echo
```

Prepare a video:

```bash
python3 scripts/prepare_video_intel.py /path/to/video.mp4 --frames 12
```

Transcribe the compact ASR audio emitted in the JSON:

```bash
python3 scripts/transcribe_elevenlabs_scribe.py --language en /tmp/video-intel-.../audio-asr.mp3
```

The helper calls ElevenLabs `scribe_v2` by default and prints sanitized JSON
containing transcript text, detected language, word timestamps, and metadata.
It does not print the API key or uploaded media payload.

## DashScope Qwen-ASR

Set credentials in your shell, never in the repo:

```bash
read -rsp "DASHSCOPE_API_KEY: " DASHSCOPE_API_KEY; export DASHSCOPE_API_KEY; echo
export DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

For custom Model Studio workspaces, set `DASHSCOPE_BASE_URL` to that
workspace's OpenAI-compatible endpoint.

Prepare a video:

```bash
python3 scripts/prepare_video_intel.py /path/to/video.mp4 --frames 12
```

Transcribe the compact ASR audio emitted in the JSON:

```bash
python3 scripts/transcribe_dashscope_qwen_asr.py /tmp/video-intel-.../audio-asr.mp3
```

The helper prints sanitized JSON containing transcript text and metadata. It
does not print the API key or encoded audio payload.

## Publishing Hygiene

Do not commit:

- API keys, bearer tokens, `.env` files, device codes, or private certificates
- source videos, extracted audio, sampled frames, transcripts, insights, or
  research artifacts
- local machine paths or private service endpoints
