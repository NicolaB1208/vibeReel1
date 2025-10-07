"""Helpers for building video cuts from AI-generated plans using ProRes intermediates."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from schemas import AI_CUT_PLAN_SCHEMA  # noqa: F401


DEFAULT_SOURCE_VIDEO = Path(
    "/Volumes/LaCie/AI Business/Videos/aemal_podcast_interview/raw_video/"
    "aemal_sayer_podcast_interview_full_recording_raw.MOV"
)
DEFAULT_CLIP_OUTPUT_DIR = Path(
    "/Volumes/LaCie/AI Business/Videos/aemal_podcast_interview/AI_clips"
)
DEFAULT_PRORES_OUTPUT_DIR = Path(
    "/Volumes/LaCie/AI Business/Videos/aemal_podcast_interview/prores_intermediates"
)
# from transcription import (
#     TranscriptionResult,
#     build_transcript_document,
#     transcribe_with_diarization,
# )


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


# def build_ai_request_payload(
#     *,
#     video_path: Path,
#     transcription_result: TranscriptionResult,
#     instructions: dict,
# ) -> dict:
#     """Create the payload expected by the external AI model."""

#     model_identifier = transcription_result.model_id or instructions.get("model_id", "unknown")

#     transcript_document = build_transcript_document(
#         source_video=video_path,
#         segments=transcription_result.segments,
#         timestamps_granularity=transcription_result.timestamps_granularity,
#         model_id=model_identifier,
#         language_code=transcription_result.language_code,
#         full_text=transcription_result.full_text,
#     )

#     return {
#         "request_id": f"ai_cut_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
#         "video_path": str(video_path),
#         "transcript": transcript_document,
#         "instructions": instructions,
#     }


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


def build_prores_transcode_command(
    *,
    source_video: Path,
    output_path: Path | None = None,
    profile: int = 3,
    pixel_format: str = "yuv422p10le",
) -> tuple[list[str], Path]:
    """Create an ffmpeg command that transcodes the source into a ProRes intermediate."""

    source_video = Path(source_video)
    if not source_video.exists():
        raise FileNotFoundError(f"Source video not found: {source_video}")

    if output_path is None:
        output_path = DEFAULT_PRORES_OUTPUT_DIR / f"{source_video.stem}_prores.mov"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-i",
        str(source_video),
        "-c:v",
        "prores_videotoolbox",
        "-profile:v",
        str(profile),
        "-pix_fmt",
        pixel_format,
        "-c:a",
        "copy",
        str(output_path),
    ]

    return command, output_path


def ensure_prores_intermediate(
    *,
    source_video: Path,
    output_path: Path | None = None,
    overwrite: bool = False,
    profile: int = 3,
    pixel_format: str = "yuv422p10le",
) -> Path:
    """Create the ProRes intermediate if it does not already exist."""

    command, target_path = build_prores_transcode_command(
        source_video=source_video,
        output_path=output_path,
        profile=profile,
        pixel_format=pixel_format,
    )

    if target_path.exists() and not overwrite:
        return target_path

    if overwrite:
        command.insert(1, "-y")
    else:
        command.insert(1, "-n")

    subprocess.run(command, check=True)
    return target_path


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
        clip_path = output_dir / f"{source_video.stem}_{cut.cut_id}.mov"
        # Legacy output-seek command kept for quick toggling:
        # command = [
        #     "ffmpeg",
        #     "-i",
        #     str(source_video),
        #     "-ss",
        #     cut.start_tc(),
        #     "-to",
        #     cut.end_tc(),
        #     "-c",
        #     "copy",
        #     "-avoid_negative_ts",
        #     "make_zero",
        #     str(clip_path),
        # ]
        command = [
            "ffmpeg",
            "-ss",
            cut.start_tc(),
            "-to",
            cut.end_tc(),
            "-i",
            str(source_video),
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
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


# def auto_edit_video(
#     source_video: Path,
#     *,
#     ai_client: Callable[[dict], dict],
#     instructions: dict,
#     transcription_kwargs: dict | None = None,
#     working_dir: Path | None = None,
# ) -> dict:
#     """End-to-end automation: transcribe, call AI, cut clips, and assemble final video."""

#     transcription_kwargs = transcription_kwargs or {}
#     working_dir = Path(working_dir or "data/output")
#     working_dir.mkdir(parents=True, exist_ok=True)

#     transcription_result = transcribe_with_diarization(
#         source_video,
#         output_dir=working_dir,
#         **transcription_kwargs,
#     )

#     ai_payload = build_ai_request_payload(
#         video_path=source_video,
#         transcription_result=transcription_result,
#         instructions=instructions,
#     )

#     cut_plan = ai_client(ai_payload)
#     cuts = validate_ai_cut_plan(cut_plan)

#     cut_commands, clip_paths = build_ffmpeg_cut_commands(
#         source_video=source_video,
#         cuts=cuts,
#         output_dir=working_dir / "clips",
#     )

#     run_ffmpeg_commands(cut_commands)

#     final_output = working_dir / f"{source_video.stem}_auto_edit.mp4"
#     concat_command, concat_list = build_concat_command(
#         clips=clip_paths,
#         output_path=final_output,
#     )
#     run_ffmpeg_commands([concat_command])

#     return {
#         "transcription": transcription_result,
#         "ai_request": ai_payload,
#         "ai_response": cut_plan,
#         "clip_paths": clip_paths,
#         "concat_list": concat_list,
#         "final_video": final_output,
#     }


def execute_cut_plan(
    *,
    source_video: Path = DEFAULT_SOURCE_VIDEO,
    cut_plan_path: Path,
    clips_dir: Path | None = None,
    final_output: Path | None = None,
    prores_output: Path | None = None,
    overwrite_prores: bool = False,
) -> dict:
    """Create clips and a final edit from an existing cut-plan JSON."""

    source_video = Path(source_video)
    if not source_video.exists():
        raise FileNotFoundError(f"Source video not found: {source_video}")

    base_stem = source_video.stem

    prores_source = ensure_prores_intermediate(
        source_video=source_video,
        output_path=prores_output,
        overwrite=overwrite_prores,
    )

    cut_plan_path = Path(cut_plan_path)
    if not cut_plan_path.exists():
        raise FileNotFoundError(f"Cut plan not found: {cut_plan_path}")

    plan_data = json.loads(cut_plan_path.read_text())
    cuts = validate_ai_cut_plan(plan_data)

    clips_dir = Path(clips_dir or DEFAULT_CLIP_OUTPUT_DIR)
    cut_commands, clip_paths = build_ffmpeg_cut_commands(
        source_video=prores_source,
        cuts=cuts,
        output_dir=clips_dir,
    )
    run_ffmpeg_commands(cut_commands)

    final_output = Path(
        final_output or (DEFAULT_CLIP_OUTPUT_DIR / f"{base_stem}_auto_edit.mov")
    )
    concat_command, concat_list = build_concat_command(
        clips=clip_paths,
        output_path=final_output,
    )
    run_ffmpeg_commands([concat_command])

    return {
        "cut_plan": plan_data,
        "cuts": cuts,
        "clip_paths": clip_paths,
        "concat_list": concat_list,
        "final_video": final_output,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate clips and a final edit from a cut-plan JSON",
    )
    parser.add_argument("cut_plan", type=Path, help="Path to the cut-plan JSON file")
    parser.add_argument(
        "--source-video",
        type=Path,
        default=DEFAULT_SOURCE_VIDEO,
        help=(
            "Path to the source video (default: "
            f"{DEFAULT_SOURCE_VIDEO}"
            ")"
        ),
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=DEFAULT_CLIP_OUTPUT_DIR,
        help=(
            "Directory to store intermediate clips "
            f"(default: {DEFAULT_CLIP_OUTPUT_DIR})"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Final output video path (default: "
            f"{DEFAULT_CLIP_OUTPUT_DIR}/<source_stem>_auto_edit.mov"
            ")"
        ),
    )
    parser.add_argument(
        "--prores-output",
        type=Path,
        default=None,
        help=(
            "ProRes intermediate output path (default: "
            f"{DEFAULT_PRORES_OUTPUT_DIR}/<source_stem>_prores.mov"
            ")"
        ),
    )
    parser.add_argument(
        "--overwrite-prores",
        action="store_true",
        help="Force regeneration of the ProRes intermediate even if it exists",
    )
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    result = execute_cut_plan(
        source_video=args.source_video,
        cut_plan_path=args.cut_plan,
        clips_dir=args.clips_dir,
        final_output=args.output,
        prores_output=args.prores_output,
        overwrite_prores=args.overwrite_prores,
    )
    print("Created clips:")
    for clip in result["clip_paths"]:
        print(f"  {clip}")
    print(f"Concat list: {result['concat_list']}")
    print(f"Final video: {result['final_video']}")


if __name__ == "__main__":
    _main()


__all__ = [
    "AI_CUT_PLAN_SCHEMA",
    "CutInstruction",
    "build_concat_command",
    "build_prores_transcode_command",
    "build_ffmpeg_cut_commands",
    "ensure_prores_intermediate",
    "execute_cut_plan",
    "milliseconds_to_timecode",
    "run_ffmpeg_commands",
    "validate_ai_cut_plan",
]
