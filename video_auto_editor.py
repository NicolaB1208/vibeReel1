"""High-level orchestration helpers for AI-assisted video editing."""

from __future__ import annotations
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

from schemas import AI_CUT_PLAN_SCHEMA
from transcription import (
    TranscriptionResult,
    build_transcript_document,
    transcribe_with_diarization,
)


@dataclass(slots=True)
class CutInstruction:
    """A single cut extracted from the AI plan."""

    cut_id: str
    start_ms: int
    end_ms: int
    source_segment_id: str | None = None
    justification: str | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def start_tc(self) -> str:
        return milliseconds_to_timecode(self.start_ms)

    def end_tc(self) -> str:
        return milliseconds_to_timecode(self.end_ms)


def milliseconds_to_timecode(value: int) -> str:
    """Convert millisecond offsets to HH:MM:SS.mmm format."""

    if value < 0:
        raise ValueError("Timestamp must be non-negative")
    total_seconds, milliseconds = divmod(int(value), 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def build_ai_request_payload(
    *,
    video_path: Path,
    transcription_result: TranscriptionResult,
    instructions: dict,
) -> dict:
    """Create the payload expected by the external AI model."""

    model_identifier = transcription_result.model_id or instructions.get("model_id", "unknown")

    transcript_document = build_transcript_document(
        source_video=video_path,
        segments=transcription_result.segments,
        timestamps_granularity=transcription_result.timestamps_granularity,
        model_id=model_identifier,
        language_code=transcription_result.language_code,
        full_text=transcription_result.full_text,
    )

    return {
        "request_id": f"ai_cut_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "video_path": str(video_path),
        "transcript": transcript_document,
        "instructions": instructions,
    }


def validate_ai_cut_plan(plan: dict) -> list[CutInstruction]:
    """Validate cut plan output from the AI model and normalize it."""

    if not isinstance(plan, dict):
        raise ValueError("Cut plan must be a dictionary")

    cuts = plan.get("cuts")
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("Cut plan must include a non-empty 'cuts' list")

    normalized: list[CutInstruction] = []
    for index, cut in enumerate(cuts, start=1):
        if not isinstance(cut, dict):
            raise ValueError(f"Cut entry at index {index} is not an object")

        cut_id = cut.get("cut_id") or f"cut_{index:04d}"
        start_ms = cut.get("start_ms")
        end_ms = cut.get("end_ms")

        if not isinstance(start_ms, (int, float)) or not isinstance(end_ms, (int, float)):
            raise ValueError(f"Cut {cut_id} must include numeric 'start_ms' and 'end_ms'")

        start_ms = int(start_ms)
        end_ms = int(end_ms)

        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError(f"Cut {cut_id} has invalid time bounds: {start_ms} -> {end_ms}")

        normalized.append(
            CutInstruction(
                cut_id=cut_id,
                start_ms=start_ms,
                end_ms=end_ms,
                source_segment_id=cut.get("source_segment_id"),
                justification=cut.get("justification"),
            )
        )

    return normalized


def build_ffmpeg_cut_commands(
    *,
    source_video: Path,
    cuts: Sequence[CutInstruction],
    output_dir: Path,
) -> tuple[list[list[str]], list[Path]]:
    """Generate ffmpeg commands that mirror the manual cutting template."""

    if not cuts:
        raise ValueError("At least one cut is required")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    clip_paths: list[Path] = []

    for cut in cuts:
        clip_path = output_dir / f"{source_video.stem}_{cut.cut_id}.mp4"
        command = [
            "ffmpeg",
            "-i",
            str(source_video),
            "-ss",
            cut.start_tc(),
            "-to",
            cut.end_tc(),
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(clip_path),
        ]
        commands.append(command)
        clip_paths.append(clip_path)

    return commands, clip_paths


def run_ffmpeg_commands(commands: Iterable[Sequence[str]]) -> None:
    """Execute ffmpeg commands sequentially, failing fast on errors."""

    for command in commands:
        subprocess.run(command, check=True)


def build_concat_command(
    *,
    clips: Sequence[Path],
    output_path: Path,
) -> tuple[list[str], Path]:
    """Create a concat demuxer list and the ffmpeg command to assemble the final cut."""

    if not clips:
        raise ValueError("No clips to concatenate")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    concat_list_path = output_path.parent / "cutlist_concat.txt"
    concat_entries = "".join(f"file '{clip}'\n" for clip in clips)
    concat_list_path.write_text(concat_entries)

    command = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list_path),
        "-c",
        "copy",
        str(output_path),
    ]
    return command, concat_list_path


def auto_edit_video(
    source_video: Path,
    *,
    ai_client: Callable[[dict], dict],
    instructions: dict,
    transcription_kwargs: dict | None = None,
    working_dir: Path | None = None,
) -> dict:
    """End-to-end automation: transcribe, call AI, cut clips, and assemble final video."""

    transcription_kwargs = transcription_kwargs or {}
    working_dir = Path(working_dir or "data/output")
    working_dir.mkdir(parents=True, exist_ok=True)

    transcription_result = transcribe_with_diarization(
        source_video,
        output_dir=working_dir,
        **transcription_kwargs,
    )

    ai_payload = build_ai_request_payload(
        video_path=source_video,
        transcription_result=transcription_result,
        instructions=instructions,
    )

    cut_plan = ai_client(ai_payload)
    cuts = validate_ai_cut_plan(cut_plan)

    cut_commands, clip_paths = build_ffmpeg_cut_commands(
        source_video=source_video,
        cuts=cuts,
        output_dir=working_dir / "clips",
    )

    run_ffmpeg_commands(cut_commands)

    final_output = working_dir / f"{source_video.stem}_auto_edit.mp4"
    concat_command, concat_list = build_concat_command(
        clips=clip_paths,
        output_path=final_output,
    )
    run_ffmpeg_commands([concat_command])

    return {
        "transcription": transcription_result,
        "ai_request": ai_payload,
        "ai_response": cut_plan,
        "clip_paths": clip_paths,
        "concat_list": concat_list,
        "final_video": final_output,
    }


__all__ = [
    "AI_CUT_PLAN_SCHEMA",
    "CutInstruction",
    "auto_edit_video",
    "build_ai_request_payload",
    "build_concat_command",
    "build_ffmpeg_cut_commands",
    "milliseconds_to_timecode",
    "run_ffmpeg_commands",
    "validate_ai_cut_plan",
]
