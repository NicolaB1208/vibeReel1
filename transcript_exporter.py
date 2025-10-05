"""Utilities for exporting simplified transcript documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_without_tokens(
    transcript_path: str | Path,
    *,
    output_path: str | Path | None = None,
    suffix: str = "_notokens",
) -> Path:
    """Write a copy of the transcript JSON without the nested token arrays."""

    source = Path(transcript_path)
    if not source.exists():
        raise FileNotFoundError(f"Transcript file not found: {source}")

    payload: dict[str, Any] = json.loads(source.read_text())
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("Transcript document is missing a 'segments' list")

    for segment in segments:
        if isinstance(segment, dict) and "tokens" in segment:
            segment.pop("tokens")

    if output_path is None:
        base = source.with_suffix("")
        destination = base.with_name(f"{base.name}{suffix}.json")
    else:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

    destination.write_text(json.dumps(payload, indent=2))
    return destination


__all__ = ["export_without_tokens"]
