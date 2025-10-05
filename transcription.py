"""Speech-to-text helpers powered by the ElevenLabs API.

This module will be implemented following test-driven development.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import httpx
from dotenv import load_dotenv


@dataclass(slots=True)
class TranscriptSegment:
    speaker: str
    start: float
    end: float
    text: str
    speaker_id: str | None = None
    tokens: list[dict] = field(default_factory=list)
    segment_type: str = "speech"
    audio_event: str | None = None


@dataclass(slots=True)
class TranscriptionResult:
    segments: list[TranscriptSegment]
    full_text: str
    language_code: str | None
    duration_seconds: float
    srt: str
    timestamps_granularity: str = "word"
    model_id: str | None = None
    json_path: Path | None = None
    srt_path: Path | None = None


def extract_audio(source_video: Path, *, sample_rate: int = 16000) -> Path:
    """Extract a mono wave track from the video for transcription."""

    if not source_video.exists():
        raise FileNotFoundError(f"Video file not found: {source_video}")

    tmp_dir = tempfile.mkdtemp(prefix="vibereel_audio_")
    output_path = Path(tmp_dir) / "audio.wav"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "wav",
        str(output_path),
    ]

    subprocess.run(command, check=True, capture_output=True)
    return output_path


def _call_elevenlabs_transcription_api(
    audio_path: Path,
    *,
    model_id: str,
    diarize: bool,
    timestamps_granularity: str = "word",
    num_speakers: int | None,
    language_code: str | None,
    diarization_threshold: float | None,
) -> dict:
    """Perform the HTTP request against ElevenLabs."""

    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY environment variable is required")

    url = "https://api.elevenlabs.io/v1/speech-to-text"

    data: dict[str, str] = {"model_id": model_id}
    data["diarize"] = json.dumps(bool(diarize))
    data["timestamps_granularity"] = timestamps_granularity

    if num_speakers is not None:
        data["num_speakers"] = str(num_speakers)
    if language_code is not None:
        data["language_code"] = language_code
    if diarization_threshold is not None:
        data["diarization_threshold"] = str(diarization_threshold)

    with audio_path.open("rb") as audio_file:
        files = {"file": (audio_path.name, audio_file, "audio/wav")}
        headers = {"xi-api-key": api_key}
        response = httpx.post(url, data=data, files=files, headers=headers, timeout=120)

    if response.status_code >= 400:
        raise RuntimeError(
            "ElevenLabs transcription failed",
            response.status_code,
            response.text,
        )

    return response.json()


def group_words_into_segments(
    words: Iterable[dict],
    *,
    max_gap: float = 0.6,
    max_duration: float | None = 12.0,
    max_tokens: int | None = 30,
) -> list[TranscriptSegment]:
    """Collapse ElevenLabs tokens into readable phrases per speaker."""

    AUDIO_EVENT_TYPES = {"audio_event", "sound"}
    PUNCTUATION_CHARS = {",", ".", "!", "?", ":", ";"}

    segments: list[TranscriptSegment] = []
    sorted_words = sorted(
        (w for w in words if "text" in w),
        key=lambda w: (w.get("start", 0.0), w.get("end", 0.0)),
    )

    current_segment: TranscriptSegment | None = None
    current_tokens: list[dict] = []
    current_parts: list[str] = []
    pending_space = False

    def finalize_current_segment() -> None:
        nonlocal current_segment, current_tokens, current_parts, pending_space
        if current_segment is None:
            return
        current_segment.text = "".join(current_parts).strip()
        current_segment.tokens = current_tokens
        segments.append(current_segment)
        current_segment = None
        current_tokens = []
        current_parts = []
        pending_space = False

    for word in sorted_words:
        raw_text = word.get("text", "")
        token_type = (word.get("type") or "word").lower()

        if token_type == "spacing":
            pending_space = True
            continue

        start_val = word.get("start")
        end_val = word.get("end", start_val)
        start_float = float(start_val) if start_val is not None else 0.0
        end_float = float(end_val) if end_val is not None else start_float
        speaker_id = word.get("speaker_id")

        if token_type in AUDIO_EVENT_TYPES:
            finalize_current_segment()
            audio_text = raw_text.strip()
            audio_segment = TranscriptSegment(
                speaker="speaker_name",
                start=start_val if start_val is not None else start_float,
                end=end_val if end_val is not None else end_float,
                text="",
                speaker_id=speaker_id,
                segment_type="audio_event",
                audio_event=audio_text,
            )
            token_payload = {
                "type": token_type,
                "text": audio_text,
                "start": start_val,
                "end": end_val,
                "speaker_id": speaker_id,
                "speaker_label": "speaker_name",
            }
            if "confidence" in word:
                token_payload["confidence"] = word["confidence"]
            audio_segment.tokens = [token_payload]
            segments.append(audio_segment)
            pending_space = False
            continue

        text = raw_text.strip()
        if not text:
            pending_space = False
            continue

        current_start_float = float(current_segment.start) if current_segment else None
        duration_if_added = (
            (end_float - current_start_float)
            if current_segment is not None and current_start_float is not None
            else None
        )

        exceeds_duration = (
            current_segment is not None
            and max_duration is not None
            and duration_if_added is not None
            and duration_if_added > max_duration
        )

        exceeds_tokens = (
            current_segment is not None
            and max_tokens is not None
            and len(current_tokens) >= max_tokens
        )

        if (
            current_segment is None
            or current_segment.speaker_id != speaker_id
            or start_float - float(current_segment.end) > max_gap
            or exceeds_duration
            or exceeds_tokens
        ):
            finalize_current_segment()
            current_segment = TranscriptSegment(
                speaker="speaker_name",
                start=start_val if start_val is not None else start_float,
                end=end_val if end_val is not None else end_float,
                text="",
                speaker_id=speaker_id,
            )
            current_tokens = []
            current_parts = []
            pending_space = False
        else:
            if pending_space and current_parts and current_parts[-1] != " ":
                current_parts.append(" ")
            current_segment.end = end_val if end_val is not None else end_float
            pending_space = False

        if current_parts:
            last_part = current_parts[-1]
            if last_part != " " and text not in PUNCTUATION_CHARS:
                current_parts.append(" ")
        current_parts.append(text)

        token_payload = {
            "type": token_type,
            "text": text,
            "start": start_val,
            "end": end_val,
            "speaker_id": speaker_id,
            "speaker_label": "speaker_name",
        }
        if "confidence" in word:
            token_payload["confidence"] = word["confidence"]
        current_tokens.append(token_payload)

    finalize_current_segment()

    return segments


def render_srt(
    segments: Iterable[TranscriptSegment],
) -> str:
    """Render an SRT-style document tailored for downstream AI consumption."""

    def format_timestamp(value: float) -> str:
        total_ms = int(round(float(value) * 1000))
        hours, remainder = divmod(total_ms, 3600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

    lines: list[str] = []
    for segment in segments:
        start_ts = format_timestamp(segment.start)
        end_ts = format_timestamp(segment.end)
        token_types = ", ".join(
            sorted({token.get("type", segment.segment_type) or segment.segment_type for token in segment.tokens})
        ) or segment.segment_type
        content = segment.audio_event if segment.segment_type == "audio_event" else segment.text
        metadata = f"[speaker_name | {segment.speaker_id or 'unknown'} | types: {token_types}]"
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(f"{metadata} {content}".strip())
        lines.append("")

    return "\n".join(lines).strip() + ("\n" if lines else "")


def build_transcript_document(
    *,
    source_video: Path,
    segments: Sequence[TranscriptSegment],
    timestamps_granularity: str,
    model_id: str,
    language_code: str | None,
    full_text: str,
) -> dict:
    """Create a structured transcript ready for downstream AI consumption."""

    return {
        "video_path": str(source_video),
        "generated_at": datetime.now().isoformat(),
        "granularity": timestamps_granularity,
        "language_code": language_code,
        "model_id": model_id,
        "segments": [
            {
                "segment_id": f"seg_{index:04d}",
                "speaker_id": segment.speaker_id,
                "speaker_label": "speaker_name",
                "start": segment.start,
                "end": segment.end,
                **(
                    {"phrase_text": segment.text}
                    if segment.segment_type != "audio_event"
                    else {"audio_event": segment.audio_event}
                ),
                "tokens": segment.tokens,
            }
            for index, segment in enumerate(segments, start=1)
        ],
        "full_text": full_text,
    }


def transcribe_with_diarization(
    source_video: Path,
    *,
    model_id: str = "scribe_v1",
    language_code: str | None = None,
    num_speakers: int | None = None,
    diarization_threshold: float | None = None,
    timestamps_granularity: str = "word",
    max_gap: float = 0.6,
    max_duration: float | None = 12.0,
    max_tokens: int | None = 30,
    output_dir: Path | None = None,
) -> TranscriptionResult:
    """Run ElevenLabs speech-to-text with diarization and return structured results."""

    audio_path: Path | None = None

    try:
        audio_path = extract_audio(source_video)

        response = _call_elevenlabs_transcription_api(
            audio_path,
            model_id=model_id,
            diarize=True,
            timestamps_granularity=timestamps_granularity,
            num_speakers=num_speakers,
            language_code=language_code,
            diarization_threshold=diarization_threshold,
        )

        words: Sequence[dict] = response.get("words", [])
        segments = group_words_into_segments(
            words,
            max_gap=max_gap,
            max_duration=max_duration,
            max_tokens=max_tokens,
        )

        srt = render_srt(segments)
        full_text = (
            response.get("text")
            or " ".join(
                segment.text for segment in segments if segment.segment_type != "audio_event"
            ).strip()
        )
        language = response.get("language_code")
        duration = float(response.get("duration", 0.0))

        if not duration and words:
            duration = max(float(word.get("end", 0.0)) for word in words)

        result = TranscriptionResult(
            segments=segments,
            full_text=full_text,
            language_code=language,
            duration_seconds=duration,
            srt=srt,
            timestamps_granularity=timestamps_granularity,
            model_id=model_id,
        )

        output_base = source_video.stem
        if output_dir is None:
            output_dir = Path("data/output")
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"{output_base}_transcript_{timestamp_suffix}.json"
        srt_path = output_dir / f"{output_base}_transcript_{timestamp_suffix}.srt"

        transcript_payload = build_transcript_document(
            source_video=source_video,
            segments=segments,
            timestamps_granularity=timestamps_granularity,
            model_id=model_id,
            language_code=language,
            full_text=full_text,
        )

        json_path.write_text(json.dumps(transcript_payload, indent=2))
        srt_path.write_text(srt)

        result.json_path = json_path
        result.srt_path = srt_path

        return result
    finally:
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
                parent = audio_path.parent
                parent.rmdir()
            except OSError:
                pass


__all__ = [
    "TranscriptSegment",
    "TranscriptionResult",
    "extract_audio",
    "group_words_into_segments",
    "render_srt",
    "build_transcript_document",
    "transcribe_with_diarization",
]
