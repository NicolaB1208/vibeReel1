from __future__ import annotations

from pathlib import Path

import pytest

from video_auto_editor import (
    CutInstruction,
    build_ffmpeg_cut_commands,
    milliseconds_to_timecode,
    validate_ai_cut_plan,
)


def test_validate_ai_cut_plan_normalizes_entries():
    plan = {
        "model_version": "test-model",
        "generated_at": "2025-01-01T00:00:00Z",
        "cuts": [
            {
                "cut_id": "intro",
                "start_ms": 2500,
                "end_ms": 7759,
                "source_segment_id": "seg_0002",
                "justification": "Opening toast",
            }
        ],
    }

    cuts = validate_ai_cut_plan(plan)

    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.cut_id == "intro"
    assert cut.start_tc() == "00:00:02.500"
    assert cut.end_tc() == "00:00:07.759"
    assert cut.source_segment_id == "seg_0002"
    assert cut.justification == "Opening toast"


def test_validate_ai_cut_plan_rejects_invalid_bounds():
    plan = {
        "model_version": "test",
        "generated_at": "now",
        "cuts": [
            {"cut_id": "bad", "start_ms": 3000, "end_ms": 2000},
        ],
    }

    with pytest.raises(ValueError):
        validate_ai_cut_plan(plan)


def test_build_ffmpeg_cut_commands_matches_template(tmp_path: Path):
    cuts = [
        CutInstruction(cut_id="intro", start_ms=2500, end_ms=7759),
    ]
    commands, clip_paths = build_ffmpeg_cut_commands(
        source_video=Path("data/raw/test_podcast_raw_video_1.mov"),
        cuts=cuts,
        output_dir=tmp_path,
    )

    assert clip_paths[0] == tmp_path / "test_podcast_raw_video_1_intro.mp4"
    assert commands[0] == [
        "ffmpeg",
        "-i",
        "data/raw/test_podcast_raw_video_1.mov",
        "-ss",
        "00:00:02.500",
        "-to",
        "00:00:07.759",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(tmp_path / "test_podcast_raw_video_1_intro.mp4"),
    ]


def test_milliseconds_to_timecode_rejects_negative():
    with pytest.raises(ValueError):
        milliseconds_to_timecode(-1)
