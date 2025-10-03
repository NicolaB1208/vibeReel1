"""Speech-to-text helpers powered by the ElevenLabs API.

This module will be implemented following test-driven development.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
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


@dataclass(slots=True)
class TranscriptionResult:
    segments: list[TranscriptSegment]
    full_text: str
    language_code: str | None
    duration_seconds: float
    srt: str


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
    timestamps_granularity: str,
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
) -> list[TranscriptSegment]:
    """Collapse word-level diarized results into readable segments."""

    segments: list[TranscriptSegment] = []
    speaker_labels: dict[str | None, str] = {}
    next_speaker_index = 1

    def get_label(speaker_id: str | None) -> str:
        nonlocal next_speaker_index
        if speaker_id not in speaker_labels:
            speaker_labels[speaker_id] = f"Speaker {next_speaker_index}"
            next_speaker_index += 1
        return speaker_labels[speaker_id]

    sorted_words = sorted(
        (w for w in words if "text" in w),
        key=lambda w: (w.get("start", 0.0), w.get("end", 0.0)),
    )

    current_segment: TranscriptSegment | None = None

    for word in sorted_words:
        text = word.get("text", "").strip()
        if not text:
            continue

        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        speaker_id = word.get("speaker_id")
        label = get_label(speaker_id)

        if (
            current_segment is None
            or current_segment.speaker != label
            or start - current_segment.end > max_gap
        ):
            if current_segment is not None:
                segments.append(current_segment)
            current_segment = TranscriptSegment(speaker=label, start=start, end=end, text=text)
        else:
            current_segment.end = end
            current_segment.text = f"{current_segment.text} {text}".strip()

    if current_segment is not None:
        segments.append(current_segment)

    return segments


def render_srt(segments: Iterable[TranscriptSegment]) -> str:
    """Render an SRT caption document out of the diarized segments."""

    def format_timestamp(value: float) -> str:
        total_ms = int(round(value * 1000))
        hours, remainder = divmod(total_ms, 3600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        start_ts = format_timestamp(segment.start)
        end_ts = format_timestamp(segment.end)
        lines.append(str(index))
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(f"{segment.speaker}: {segment.text}")
        lines.append("")

    return "\n".join(lines).strip() + ("\n" if lines else "")


def transcribe_with_diarization(
    source_video: Path,
    *,
    model_id: str = "scribe_v1",
    language_code: str | None = None,
    num_speakers: int | None = None,
    diarization_threshold: float | None = None,
) -> TranscriptionResult:
    """Run ElevenLabs speech-to-text with diarization and return structured results."""

    audio_path: Path | None = None

    try:
        audio_path = extract_audio(source_video)

        response = _call_elevenlabs_transcription_api(
            audio_path,
            model_id=model_id,
            diarize=True,
            timestamps_granularity="word",
            num_speakers=num_speakers,
            language_code=language_code,
            diarization_threshold=diarization_threshold,
        )

        words: Sequence[dict] = response.get("words", [])
        segments = group_words_into_segments(words)

        srt = render_srt(segments)
        full_text = response.get("text") or " ".join(word.get("text", "") for word in words).strip()
        language = response.get("language_code")
        duration = float(response.get("duration", 0.0))

        if not duration and words:
            duration = max(float(word.get("end", 0.0)) for word in words)

        return TranscriptionResult(
            segments=segments,
            full_text=full_text,
            language_code=language,
            duration_seconds=duration,
            srt=srt,
        )
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
    "transcribe_with_diarization",
]
