---
name: video-intel
description: Analyze videos by extracting audio, transcribing speech with a configured speech-to-text backend such as ElevenLabs Scribe or Alibaba Cloud Model Studio Qwen-ASR, sampling and optionally preserving representative frames, visually inspecting those frames, returning content analysis in chat, supporting post-analysis Q&A with online research, and optionally creating Markdown insight/transcript/frame-analysis/research documents when requested. Use when the user asks what a video is about, wants a video summary, scene breakdown, spoken-content summary, visual-content analysis, frame-by-frame analysis, combined audio/video understanding, post-analysis Q&A about the video's subject, or analysis artifacts for local video files such as .mp4, .mov, .mkv, .webm, .avi, or screen recordings.
---

# Video Intel

Use this skill to understand a local video by combining transcript evidence with visual frame evidence. The default deliverable is chat output. Create separate report files only when the user explicitly asks for them, and do so after finishing the analysis.

## Workflow

1. Identify the target video path from the user request. If multiple plausible files exist, inspect names, sizes, and modification times before choosing; ask only if the target remains ambiguous.
2. Prepare media with the bundled helper from this skill directory:

   ```bash
   python3 scripts/prepare_video_intel.py /path/to/video --frames 12
   ```

   The script creates a temp folder, extracts canonical audio at 48 kHz mono WAV, creates a compact `audio-asr.mp3` for cloud ASR, samples frames, and prints JSON containing the generated paths.
3. Transcribe the extracted `asr_audio.path` with the configured speech-to-text backend when available. Prefer ElevenLabs Scribe when `ELEVENLABS_API_KEY` is set:

   ```bash
   read -rsp "ELEVENLABS_API_KEY: " ELEVENLABS_API_KEY; export ELEVENLABS_API_KEY; echo
   python3 scripts/transcribe_elevenlabs_scribe.py --language en /tmp/video-intel-.../audio-asr.mp3
   ```

   Use Alibaba Cloud Model Studio Qwen-ASR when `DASHSCOPE_API_KEY` or `ALIBABA_API_KEY` is set:

   ```bash
   read -rsp "DASHSCOPE_API_KEY: " DASHSCOPE_API_KEY; export DASHSCOPE_API_KEY; echo
   # Optional for custom workspaces/regions:
   # export DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
   python3 scripts/transcribe_dashscope_qwen_asr.py /tmp/video-intel-.../audio-asr.mp3
   ```

   The helpers print sanitized JSON with transcript text and provider metadata. The ElevenLabs helper uses `scribe_v2` by default and includes word-level timestamps when returned. The DashScope helper uses the OpenAI-compatible `qwen3-asr-flash` path and includes `annotations` and `usage` when returned. Audio larger than a helper's size limit should be compressed further, hosted at a public URL, or routed through an asynchronous ASR workflow. Never print API keys, bearer tokens, certificate contents, private keys, device codes, encoded audio payloads, or the contents of `.env`. If transcription is unavailable, report that transcript evidence is unavailable and continue with visual analysis rather than fabricating speech.
4. Inspect sampled frames with `view_image`. Prefer all frames for short videos and a representative subset for long or repetitive videos. Use frame timestamps from the script output when describing the timeline.
5. If transcription is still running and the user asks for more confidence, sample more frames or create a contact sheet instead of starting another transcription request.
6. Synthesize the video meaning from both channels. Treat transcript and visuals as separate evidence streams; call out conflicts, unclear audio, missing speech, black frames, slides, UI screens, or repeated scenes.
7. If the user asks to keep frames or analysis artifacts, create a single per-video bundle folder named after the video basename. Put the source video, Markdown documents, and frame artifacts inside that folder so one video maps to one self-contained directory.
8. If the user asks to keep frames, preserve them under `frames/` inside the bundle folder. Keep a clean structure such as `frames/sampled/`, `frames/targeted/`, and optional `frames/contact-sheet-*.jpg`; remove duplicate temporary helper output unless the user asks to keep raw workdirs.
9. If the user asks for Markdown artifacts, create them only after the analysis is complete. A useful default inside the bundle folder is `insights.md` with the video interpretation, `transcription.md` with the raw transcript plus a short note about transcription quality, and `frame-analysis.md` when frame-by-frame evidence is requested.
10. If a post-analysis Q&A round begins and the question depends on the broader subject, research the subject online before answering. Create or update `research.md` inside the bundle folder with sources, findings, and how the research changes or confirms the video interpretation.

## Analysis Standards

- Ground claims in observed evidence: transcript phrases, frame timestamps, visible objects, people, actions, UI screens, slides, charts, locations, or scene changes.
- Distinguish facts from inference. Use phrasing like "appears to" when identity, intent, location, or context is not certain.
- Do not identify unknown private people by name unless the video or user provides the identity.
- If the video is a tutorial, meeting, demo, lecture, ad, vlog, game clip, or surveillance-style clip, adapt the summary to that genre.
- If the transcript contains sensitive material, summarize only what is needed for the user's request.
- Clean up temporary files only when they are clearly disposable and no further inspection is needed.

## Post-Analysis Q&A Research

When the user asks follow-up questions after the video has been analyzed, decide whether the answer requires only the video artifacts or broader subject knowledge.

- For questions about what the video said or showed, answer from `insights.md`, `transcription.md`, `frame-analysis.md`, and preserved frames.
- For questions about the underlying subject, market, codebase, claims, feasibility, risks, competitors, terminology, standards, or current state of the domain, do online research first.
- Prefer primary sources: project repositories/docs, protocol documentation, standards/specs, technical papers, audits, official product docs, credible market/regulatory sources, and source code. Use secondary sources only for context.
- Record the research in `research.md` inside the same bundle folder before or while answering. Include source links, retrieval date, key findings, relevance to the video, confidence level, and open questions.
- For platform-specific follow-ups, research both exact analogs and underlying primitives. If exact analogs do not appear to exist, say so carefully and document the closest primitives, terminology mappings, and implementation differences.
- Check the speaker's assumptions explicitly when the user asks for validation. Add an "Assumption Checks" section covering what is true, partly true, misleading, or unsupported. Be precise about domain terms such as limit order, stop/trigger order, market order, smart contract vs on-chain program, oracle, keeper, vault, and executor.
- In chat, answer the user's question directly and cite the research document path plus the key sources used.
- If browsing is unavailable, say so and separate video-grounded analysis from unverified background knowledge.

## Evidence-First Follow-Up Dialogue

When a user asks iterative clarifying questions after the initial analysis, keep returning to the artifacts before expanding the answer.

- Start with what the video explicitly says or shows. Use transcript wording, frame timestamps, visible diagrams, on-screen code, UI labels, and speaker caveats as evidence.
- If an earlier assumption changes, restate the corrected assumption and re-evaluate the answer under that premise. Do not carry forward platform, launch-status, architecture, or role assumptions that the video evidence contradicts.
- For conceptual confusion, simplify the mechanism into actors, assets, conditions, actions, and outcomes before reintroducing technical terms.
- When asked what is unclear, split findings into "Answered By The Video" and "Still Not Fully Clear." Keep unresolved items focused on what the artifacts do not specify, not on unrelated external risks.
- Distinguish a user's interpretation from the speaker's claim and from outside-domain facts. If the speaker uses an imprecise analogy, explain the analogy's useful part and its limit.
- If the question can be answered from artifacts alone, do not browse. If external comparison is needed, research first and then map external findings back to the video evidence.

## Chat Output Shape

Keep the response concise unless the user asks for detail:

- **What it is:** one or two sentences.
- **Spoken content:** summarize the transcript, noting if there was no speech or transcription failed.
- **Visual content:** summarize key scenes or frame timeline.
- **Overall takeaway:** explain what the video is about and any obvious purpose, audience, or next action.

For longer videos, include a timestamped scene list before the takeaway.

## Optional Markdown Artifacts

When requested, place artifacts in one folder per source video unless the user specifies another directory. Use the video basename as the folder name and simple artifact names inside it, for example:

```text
<video basename>/
  video.<ext>
  insights.md
  transcription.md
  frame-analysis.md
  research.md
  frames/
    contact-sheet-15s.jpg
    sampled/
    targeted/
```

The insights document should include the evidence used, visual timeline, spoken-content summary, key takeaways, and uncertainties. The transcription document should include the raw transcript text, the provider/model used when known, and obvious transcription artifacts without silently rewriting the transcript.

When the user asks for frame-by-frame analysis, keep the frames and analyze every preserved frame in the frame-analysis document. Include timestamp, file path, visible content, what changed from nearby frames, and why that frame matters. End the document by connecting the frame evidence to the transcript and explaining the larger meaning of the video.

When the user asks post-analysis questions that require broader context, add `research.md` to the same bundle. Do not treat the original video as sufficient evidence for external claims; use online sources and mark what is confirmed, contradicted, or still uncertain.
