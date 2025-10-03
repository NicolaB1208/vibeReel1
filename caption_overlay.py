"""Utility to burn SRT subtitles into the combined vertical video."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    *,
    font_size: int = 54,
    margin_v: int = 0,
) -> Path:
    """Burn the provided SRT subtitles into the video using ffmpeg."""

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    subtitle_filter = (
        "subtitles="
        f"{subtitle_path.as_posix()}:"
        "force_style='Alignment=5,BorderStyle=3,Outline=3,OutlineColour=&H40000000,"
        f"Shadow=0,Fontsize={font_size},MarginV={margin_v}'"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        subtitle_filter,
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

    subprocess.run(command, check=True, capture_output=True)
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
