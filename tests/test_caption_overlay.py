from __future__ import annotations

from pathlib import Path

import pytest

import caption_overlay


def test_burn_subtitles_invokes_ffmpeg(monkeypatch, tmp_path: Path):
    video = tmp_path / "video.mp4"
    subs = tmp_path / "subs.srt"
    output = tmp_path / "out.mp4"

    video.write_bytes(b"fake")
    subs.write_text("1\n00:00:00,000 --> 00:00:01,000\nTest\n")

    captured = {}

    ass_file = tmp_path / "temp.ass"
    ass_file.write_text("dummy")

    def fake_create(path, font_size, margin_v):
        captured["font_size"] = font_size
        captured["margin_v"] = margin_v
        return ass_file

    def fake_run(cmd, check, capture_output):
        captured["cmd"] = cmd
        output.write_bytes(b"")
        return None

    monkeypatch.setattr(caption_overlay, "_create_ass_from_srt", fake_create)
    monkeypatch.setattr(caption_overlay.subprocess, "run", fake_run)

    caption_overlay.burn_subtitles(video, subs, output, font_size=40, margin_v=10)

    assert captured["cmd"][0] == "ffmpeg"
    filter_arg = captured["cmd"][captured["cmd"].index("-vf") + 1]
    assert filter_arg.startswith("ass=")
    assert captured["font_size"] == 40
    assert captured["margin_v"] == 10
    assert output.exists()
    assert not ass_file.exists()


def test_burn_subtitles_missing_input(tmp_path: Path):
    video = tmp_path / "missing.mp4"
    subs = tmp_path / "subs.srt"
    subs.write_text("dummy")

    with pytest.raises(FileNotFoundError):
        caption_overlay.burn_subtitles(video, subs, tmp_path / "out.mp4")
