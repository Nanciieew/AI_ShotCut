# Whisper Adapter

## Responsibility

Speech-to-text transcription. Generates subtitle segments with word-level
timestamps from the audio track.

## Input

- Audio file (WAV, 16 kHz mono preferred).
- OR existing subtitle file (SRT, ASS, WebVTT) for direct parsing.

## Output

`subtitles.json` — array of subtitle segments with:
- `subtitle_id`, `start_ms`, `end_ms`, `text`
- `language`, `confidence`
- Optional word-level timestamps

## Constraints

- Must NOT perform speaker identification.
- Must NOT perform intent/emotion analysis.
- Whisper timestamps may drift on long videos — treat as auxiliary evidence.
- Subtitle timestamps are NOT used as final cut points directly.

## Access Method

See project root `third_party/README.md`.

## License

OpenAI Whisper: MIT license.
