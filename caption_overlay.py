"""Utility to burn SRT subtitles into the combined vertical video."""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


TIME_PATTERN = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})\s+-->\s+(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)


def _seconds_to_ass_time(seconds: float) -> str:
    total_cs = int(round(seconds * 100))
    hours, remainder = divmod(total_cs, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _parse_srt(subtitle_path: Path) -> list[tuple[float, float, str]]:
    blocks = []
    with subtitle_path.open("r", encoding="utf-8") as handle:
        content = handle.read()

    entries = re.split(r"\r?\n\r?\n", content.strip())
    for entry in entries:
        lines = entry.strip().splitlines()
        if len(lines) < 2:
            continue
        time_line_index = 1 if lines[0].strip().isdigit() else 0
        time_line = lines[time_line_index]
        match = TIME_PATTERN.match(time_line.strip())
        if not match:
            continue

        def to_seconds(prefix: str) -> float:
            hours = int(match.group(f"{prefix}h"))
            minutes = int(match.group(f"{prefix}m"))
            seconds = int(match.group(f"{prefix}s"))
            ms = int(match.group(f"{prefix}ms"))
            return hours * 3600 + minutes * 60 + seconds + ms / 1000

        start = to_seconds("")
        end = to_seconds("e")
        text_lines = lines[time_line_index + 1 :]
        text = "\\N".join(line.strip() for line in text_lines if line.strip())
        if text:
            blocks.append((start, end, text))

    return blocks


def _create_ass_from_srt(
    subtitle_path: Path,
    *,
    font_size: int,
    margin_v: int,
) -> Path:
    cues = _parse_srt(subtitle_path)
    if not cues:
        raise ValueError("Subtitle file contains no cues")

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 2160
PlayResY: 3840

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,{font_size},&H00FFFFFF,&H000000FF,&H66000000,&H00000000,0,0,0,0,100,100,0,0,3,4,0,5,0,0,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with tempfile.NamedTemporaryFile("w", suffix=".ass", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(header.format(font_size=font_size, margin_v=margin_v))
        for start, end, text in cues:
            start_ass = _seconds_to_ass_time(start)
            end_ass = _seconds_to_ass_time(end)
            safe_text = text.replace("{", r"\{").replace("}", r"\}")
            temp_file.write(
                f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,{margin_v},, {safe_text}\n"
            )
        ass_path = Path(temp_file.name)

    return ass_path


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    *,
    font_size: int = 54,
    margin_v: int = 0,
) -> Path:
    """Burn the provided subtitles into the video using ffmpeg."""

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ass_path = _create_ass_from_srt(subtitle_path, font_size=font_size, margin_v=margin_v)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"ass={ass_path.as_posix()}",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "copy",
        str(output_path),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True)
    finally:
        try:
            ass_path.unlink()
        except OSError:
            pass

    return output_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Burn transcript subtitles into a video.")
    parser.add_argument(
        "video",
        type=Path,
        nargs="?",
        default=Path("data/output/combined_vertical.mp4"),
        help="Path to the combined vertical video.",
    )
    parser.add_argument(
        "subtitle",
        type=Path,
        nargs="?",
        default=Path("data/output/transcript.srt"),
        help="Path to the transcript SRT file.",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=Path("data/output/combined_with_subs.mp4"),
        help="Path for the video with burned subtitles.",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=54,
        help="Font size used for the subtitle overlay.",
    )
    parser.add_argument(
        "--margin-v",
        type=int,
        default=0,
        help="Vertical margin applied to subtitles (in pixels).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    burn_subtitles(
        args.video,
        args.subtitle,
        args.output,
        font_size=args.font_size,
        margin_v=args.margin_v,
    )


if __name__ == "__main__":
    main()
