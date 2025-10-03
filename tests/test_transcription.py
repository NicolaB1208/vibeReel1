from __future__ import annotations

from pathlib import Path

import pytest

import transcription
from transcription import TranscriptSegment


def test_group_words_into_segments_merges_adjacent_words():
    words = [
        {
            "text": "Hello",
            "start": 0.0,
            "end": 0.4,
            "speaker_id": "speaker_0",
        },
        {
            "text": "world",
            "start": 0.45,
            "end": 0.9,
            "speaker_id": "speaker_0",
        },
        {
            "text": "Hi",
            "start": 1.6,
            "end": 2.1,
            "speaker_id": "speaker_1",
        },
    ]

    segments = transcription.group_words_into_segments(words, max_gap=0.75)

    assert segments == [
        TranscriptSegment(speaker="Speaker 1", start=0.0, end=0.9, text="Hello world"),
        TranscriptSegment(speaker="Speaker 2", start=1.6, end=2.1, text="Hi"),
    ]


def test_render_srt_formats_segments_in_order():
    segments = [
        TranscriptSegment(speaker="Speaker 1", start=0.0, end=1.25, text="Hello world"),
        TranscriptSegment(speaker="Speaker 2", start=1.5, end=3.0, text="How are you"),
    ]

    srt = transcription.render_srt(segments)

    assert "1\n00:00:00,000 --> 00:00:01,250\nSpeaker 1: Hello world" in srt
    assert "2\n00:00:01,500 --> 00:00:03,000\nSpeaker 2: How are you" in srt


def test_transcribe_with_diarization_parses_response(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"test")

    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"wave")

    sample_response = {
        "language_code": "en",
        "language_probability": 0.99,
        "duration": 5.0,
        "text": "Hello world Hi there",
        "words": [
            {
                "text": "Hello",
                "start": 0.0,
                "end": 0.5,
                "speaker_id": "speaker_0",
            },
            {
                "text": "world",
                "start": 0.6,
                "end": 1.0,
                "speaker_id": "speaker_0",
            },
            {
                "text": "Hi",
                "start": 2.0,
                "end": 2.4,
                "speaker_id": "speaker_1",
            },
            {
                "text": "there",
                "start": 2.5,
                "end": 3.0,
                "speaker_id": "speaker_1",
            },
        ],
    }

    captured_payload = {}

    def fake_extract_audio(path: Path, *, sample_rate: int = 16000) -> Path:
        assert path == video_path
        return audio_path

    def fake_call_api(
        audio: Path,
        *,
        model_id: str,
        diarize: bool,
        timestamps_granularity: str,
        num_speakers: int | None,
        language_code: str | None,
        diarization_threshold: float | None,
    ) -> dict:
        assert audio == audio_path
        captured_payload.update(
            {
                "model_id": model_id,
                "diarize": diarize,
                "timestamps_granularity": timestamps_granularity,
                "num_speakers": num_speakers,
                "language_code": language_code,
                "diarization_threshold": diarization_threshold,
            }
        )
        return sample_response

    monkeypatch.setattr(transcription, "extract_audio", fake_extract_audio)
    monkeypatch.setattr(transcription, "_call_elevenlabs_transcription_api", fake_call_api)

    result = transcription.transcribe_with_diarization(
        video_path,
        model_id="scribe_v1",
        num_speakers=2,
        language_code="en",
    )

    assert captured_payload["diarize"] is True
    assert captured_payload["timestamps_granularity"] == "word"
    assert captured_payload["num_speakers"] == 2
    assert result.language_code == "en"
    assert result.full_text == "Hello world Hi there"
    assert [seg.text for seg in result.segments] == ["Hello world", "Hi there"]
    assert "Speaker 1" in result.srt
    assert result.duration_seconds == pytest.approx(5.0)
