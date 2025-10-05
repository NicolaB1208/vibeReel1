"""JSON schema definitions shared across the auto-editing pipeline."""

from __future__ import annotations

TRANSCRIPT_DOCUMENT_SCHEMA: dict = {
    "type": "object",
    "required": [
        "video_path",
        "generated_at",
        "granularity",
        "language_code",
        "model_id",
        "segments",
        "full_text",
    ],
    "properties": {
        "video_path": {"type": "string"},
        "generated_at": {"type": "string"},
        "granularity": {"type": "string"},
        "language_code": {"type": ["string", "null"]},
        "model_id": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "segment_id",
                    "speaker_id",
                    "speaker_label",
                    "start",
                    "end",
                    "tokens",
                ],
                "properties": {
                    "segment_id": {"type": "string"},
                    "speaker_id": {"type": ["string", "null"]},
                    "speaker_label": {"type": "string"},
                    "start": {"type": ["number", "integer"]},
                    "end": {"type": ["number", "integer"]},
                    "phrase_text": {"type": "string"},
                    "audio_event": {"type": "string"},
                    "tokens": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": [
                                "type",
                                "text",
                                "start",
                                "end",
                                "speaker_id",
                                "speaker_label",
                            ],
                            "properties": {
                                "type": {"type": "string"},
                                "text": {"type": "string"},
                                "start": {"type": ["number", "integer"]},
                                "end": {"type": ["number", "integer"]},
                                "speaker_id": {"type": ["string", "null"]},
                                "speaker_label": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "anyOf": [
                    {"required": ["phrase_text"]},
                    {"required": ["audio_event"]},
                ],
                "additionalProperties": False,
            },
        },
        "full_text": {"type": "string"},
    },
    "additionalProperties": False,
}

TRANSCRIPT_DOCUMENT_SCHEMA_NO_TOKENS: dict = {
    "type": "object",
    "required": [
        "video_path",
        "generated_at",
        "granularity",
        "language_code",
        "model_id",
        "segments",
        "full_text",
    ],
    "properties": {
        "video_path": {"type": "string"},
        "generated_at": {"type": "string"},
        "granularity": {"type": "string"},
        "language_code": {"type": ["string", "null"]},
        "model_id": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "segment_id",
                    "speaker_id",
                    "speaker_label",
                    "start",
                    "end",
                ],
                "properties": {
                    "segment_id": {"type": "string"},
                    "speaker_id": {"type": ["string", "null"]},
                    "speaker_label": {"type": "string"},
                    "start": {"type": ["number", "integer"]},
                    "end": {"type": ["number", "integer"]},
                    "phrase_text": {"type": "string"},
                    "audio_event": {"type": "string"},
                },
                "anyOf": [
                    {"required": ["phrase_text"]},
                    {"required": ["audio_event"]},
                ],
                "additionalProperties": False,
            },
        },
        "full_text": {"type": "string"},
    },
    "additionalProperties": False,
}

AI_CUT_PLAN_SCHEMA: dict = {
    "type": "object",
    "required": ["model_version", "generated_at", "cuts"],
    "properties": {
        "model_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "notes": {"type": "string"},
        "cuts": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["cut_id", "start_ms", "end_ms"],
                "properties": {
                    "cut_id": {"type": "string"},
                    "source_segment_id": {"type": ["string", "null"]},
                    "start_ms": {"type": "integer", "minimum": 0},
                    "end_ms": {"type": "integer", "minimum": 0},
                    "justification": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

__all__ = [
    "TRANSCRIPT_DOCUMENT_SCHEMA",
    "TRANSCRIPT_DOCUMENT_SCHEMA_NO_TOKENS",
    "AI_CUT_PLAN_SCHEMA",
]
