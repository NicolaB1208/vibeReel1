import subprocess
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for

BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "output"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

app = Flask(__name__)

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _first_video() -> Optional[Path]:
    for path in sorted(VIDEO_DIR.iterdir()):
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            return path
    return None


def _video_mime(path: Path) -> str:
    mapping = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".m4v": "video/x-m4v",
    }
    return mapping.get(path.suffix.lower(), "video/mp4")


def _probe_dimensions(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    parts = [segment for segment in result.stdout.strip().split("x") if segment]
    if len(parts) < 2:
        raise ValueError(f"Unexpected ffprobe output: {result.stdout!r}")
    width_str, height_str = parts[:2]
    return int(width_str), int(height_str)


@app.route("/")
def index():
    video_path = _first_video()
    video_url = None
    video_mime = None
    if video_path:
        video_url = url_for("serve_video", filename=video_path.name)
        video_mime = _video_mime(video_path)
    return render_template("index.html", video_url=video_url, video_mime=video_mime)


@app.route("/media/<path:filename>")
def serve_video(filename: str):
    return send_from_directory(VIDEO_DIR, filename)


@app.route("/outputs/<path:filename>")
def serve_output(filename: str):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.route("/process", methods=["POST"])
def process_video():
    video_path = _first_video()
    if not video_path:
        return jsonify({"error": "No source video available. Place a file in data/raw."}), 400

    payload = request.get_json(silent=True)
    if not payload or "regions" not in payload:
        return jsonify({"error": "Missing region data."}), 400

    regions = payload["regions"]
    if not isinstance(regions, list) or len(regions) != 2:
        return jsonify({"error": "Exactly two regions must be provided."}), 400

    try:
        video_width, video_height = _probe_dimensions(video_path)
    except subprocess.CalledProcessError as exc:
        return jsonify({"error": "Unable to read video metadata.", "details": exc.stderr}), 500
    except ValueError as exc:
        return jsonify({"error": "Unable to parse video dimensions.", "details": str(exc)}), 500

    outputs = []
    for index, region in enumerate(regions, start=1):
        try:
            x_ratio = float(region["x"])
            y_ratio = float(region["y"])
            width_ratio = float(region["width"])
            height_ratio = float(region["height"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid region data provided."}), 400

        crop_width = int(round(width_ratio * video_width))
        crop_height = int(round(height_ratio * video_height))
        crop_x = int(round(x_ratio * video_width))
        crop_y = int(round(y_ratio * video_height))

        crop_width = max(1, min(crop_width, video_width))
        crop_height = max(1, min(crop_height, video_height))
        crop_x = max(0, min(crop_x, video_width - crop_width))
        crop_y = max(0, min(crop_y, video_height - crop_height))

        output_name = f"segment_{index}.mp4"
        output_path = OUTPUT_DIR / output_name

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}",
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
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            return (
                jsonify(
                    {
                        "error": "ffmpeg failed while exporting the cropped video.",
                        "details": exc.stderr.decode("utf-8", errors="ignore"),
                    }
                ),
                500,
            )

        outputs.append(
            {
                "label": f"Speaker {index}",
                "filename": output_name,
                "url": url_for("serve_output", filename=output_name),
                "crop": {
                    "x": crop_x,
                    "y": crop_y,
                    "width": crop_width,
                    "height": crop_height,
                },
            }
        )

    return jsonify({"outputs": outputs})


if __name__ == "__main__":
    app.run(debug=True)
