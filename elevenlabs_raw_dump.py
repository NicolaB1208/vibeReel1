"""Utility helpers for capturing ElevenLabs raw responses for manual inspection."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from transcription import _call_elevenlabs_transcription_api, extract_audio

RAW_CAPTURE_DIR = Path("data/raw")


def save_raw_elevenlabs_transcription(
    source_video: str | Path,
    *,
    model_id: str = "scribe_v1",
    language_code: str | None = None,
    num_speakers: int | None = None,
    diarization_threshold: float | None = None,
    timestamps_granularity: str = "word",
    output_path: str | Path | None = None,
) -> Path:
    """Call ElevenLabs and persist the untouched JSON payload for quick debugging."""

    video_path = Path(source_video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    resolved_output = Path(output_path) if output_path else RAW_CAPTURE_DIR / (
        f"elevenlabs_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    audio_path: Path | None = None

    try:
        audio_path = extract_audio(video_path)
        response = _call_elevenlabs_transcription_api(
            audio_path,
            model_id=model_id,
            diarize=True,
            timestamps_granularity=timestamps_granularity,
            num_speakers=num_speakers,
            language_code=language_code,
            diarization_threshold=diarization_threshold,
        )
        resolved_output.write_text(json.dumps(response, indent=2))
    finally:
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
                audio_path.parent.rmdir()
            except OSError:
                pass

    return resolved_output


__all__ = ["save_raw_elevenlabs_transcription"]
