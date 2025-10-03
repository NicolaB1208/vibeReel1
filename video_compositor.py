"""Utilities for composing exported clips into a single stacked video."""

from __future__ import annotations

import subprocess
from pathlib import Path

CANVAS_WIDTH = 2160
CANVAS_HEIGHT = 3840
TOP_BOTTOM_PADDING = 103
TARGET_ASPECT_RATIO = 1.1

INNER_HEIGHT = CANVAS_HEIGHT - 2 * TOP_BOTTOM_PADDING
CLIP_HEIGHT = INNER_HEIGHT // 2
CLIP_WIDTH = round(CLIP_HEIGHT * TARGET_ASPECT_RATIO)


def compose_vertical_stack(top_clip: Path, bottom_clip: Path, output_path: Path) -> Path:
    """Combine two clips into a single 4K vertical video.

    Args:
        top_clip: Path to the clip that should appear in the upper half.
        bottom_clip: Path to the clip that should appear in the lower half.
        output_path: Target path for the composed video.

    Returns:
        The ``output_path`` once the ffmpeg process completes successfully.

    Raises:
        subprocess.CalledProcessError: If ffmpeg exits with a non-zero status.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    filter_complex = \
        (
            f"[0:v]scale={CLIP_WIDTH}:{CLIP_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={CLIP_WIDTH}:{CLIP_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];"
            f"[1:v]scale={CLIP_WIDTH}:{CLIP_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={CLIP_WIDTH}:{CLIP_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];"
            f"[v0][v1]vstack=inputs=2[stack];"
            f"[stack]pad={CANVAS_WIDTH}:{CANVAS_HEIGHT}:(ow-iw)/2:{TOP_BOTTOM_PADDING}:color=black[outv]"
        )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(top_clip),
        "-i",
        str(bottom_clip),
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output_path),
    ]

    subprocess.run(command, check=True, capture_output=True)
    return output_path


__all__ = [
    "compose_vertical_stack",
    "CANVAS_WIDTH",
    "CANVAS_HEIGHT",
    "CLIP_WIDTH",
    "CLIP_HEIGHT",
    "TOP_BOTTOM_PADDING",
]
