from __future__ import annotations

import json
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

    assert len(segments) == 2

    first, second = segments
    assert first.speaker == "speaker_name"
    assert first.speaker_id == "speaker_0"
    assert first.text == "Hello world"
    assert first.segment_type == "speech"
    assert [token["text"] for token in first.tokens] == ["Hello", "world"]
    assert all("start_ms" not in token for token in first.tokens)
    assert all(token["speaker_label"] == "speaker_name" for token in first.tokens)

    assert second.speaker == "speaker_name"
    assert second.speaker_id == "speaker_1"
    assert second.text == "Hi"
    assert [token["text"] for token in second.tokens] == ["Hi"]
    assert second.segment_type == "speech"


def test_render_srt_formats_segments_in_order():
    segments = [
        TranscriptSegment(
            speaker="speaker_name",
            start=0.079,
            end=2.079,
            text="Thank you",
            speaker_id="speaker_0",
            tokens=[
                {
                    "type": "word",
                    "text": "Thank",
                    "start": 0.079,
                    "end": 0.219,
                    "speaker_id": "speaker_0",
                    "speaker_label": "speaker_name",
                },
                {
                    "type": "word",
                    "text": "you",
                    "start": 0.239,
                    "end": 0.299,
                    "speaker_id": "speaker_0",
                    "speaker_label": "speaker_name",
                },
            ],
        ),
        TranscriptSegment(
            speaker="speaker_name",
            start=5.059,
            end=6.5,
            text="",
            speaker_id="speaker_0",
            tokens=[
                {
                    "type": "audio_event",
                    "text": "(laughs)",
                    "start": 5.059,
                    "end": 6.5,
                    "speaker_id": "speaker_0",
                    "speaker_label": "speaker_name",
                }
            ],
            segment_type="audio_event",
            audio_event="(laughs)",
        ),
    ]

    srt = transcription.render_srt(segments)

    assert "00:00:00.079 --> 00:00:02.079" in srt
    assert "[speaker_name | speaker_0 | types: word] Thank you" in srt
    assert "00:00:05.059 --> 00:00:06.500" in srt
    assert "[speaker_name | speaker_0 | types: audio_event] (laughs)" in srt


def test_group_words_into_segments_separates_audio_events():
    words = [
        {
            "text": "Yeah",
            "start": 6.639,
            "end": 6.919,
            "speaker_id": "speaker_0",
            "type": "word",
        },
        {
            "text": "Cheers!",
            "start": 6.919,
            "end": 7.319,
            "speaker_id": "speaker_0",
            "type": "word",
        },
        {
            "text": "(glass clanks)",
            "start": 7.4,
            "end": 7.8,
            "speaker_id": "speaker_0",
            "type": "audio_event",
        },
    ]

    segments = transcription.group_words_into_segments(words)

    assert len(segments) == 2
    speech_segment, event_segment = segments
    assert speech_segment.segment_type == "speech"
    assert speech_segment.text == "Yeah Cheers!"
    assert event_segment.segment_type == "audio_event"
    assert event_segment.audio_event == "(glass clanks)"
    assert event_segment.tokens[0]["type"] == "audio_event"


def test_group_words_into_segments_enforces_max_tokens():
    words = [
        {"text": "one", "start": 0.0, "end": 0.3, "speaker_id": "speaker_0"},
        {"text": "two", "start": 0.4, "end": 0.7, "speaker_id": "speaker_0"},
        {"text": "three", "start": 0.8, "end": 1.1, "speaker_id": "speaker_0"},
    ]

    segments = transcription.group_words_into_segments(
        words,
        max_gap=1.0,
        max_tokens=2,
    )

    assert len(segments) == 2
    assert segments[0].text == "one two"
    assert segments[1].text == "three"


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

    output_dir = tmp_path / "artifacts"

    result = transcription.transcribe_with_diarization(
        video_path,
        model_id="scribe_v1",
        num_speakers=2,
        language_code="en",
        output_dir=output_dir,
    )

    assert captured_payload["diarize"] is True
    assert captured_payload["timestamps_granularity"] == "word"
    assert captured_payload["num_speakers"] == 2
    assert result.language_code == "en"
    assert result.full_text == "Hello world Hi there"
    assert [seg.text for seg in result.segments] == ["Hello world", "Hi there"]
    assert "00:00:00.000 --> 00:00:01.000" in result.srt
    assert "[speaker_name | speaker_0 | types: word] Hello world" in result.srt
    assert result.duration_seconds == pytest.approx(5.0)
    assert result.json_path is not None and result.json_path.exists()
    assert result.srt_path is not None and result.srt_path.exists()

    payload = json.loads(result.json_path.read_text())
    assert payload["segments"][0]["tokens"][0]["type"] == "word"
    assert all(token.get("type") != "spacing" for token in payload["segments"][0]["tokens"])
    assert "start_ms" not in payload["segments"][0]
    assert "start_ms" not in payload["segments"][0]["tokens"][0]
    assert "logprob" not in payload["segments"][0]["tokens"][0]
    assert payload["segments"][0]["speaker_label"] == "speaker_name"
