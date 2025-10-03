# vibeReel1

Prototype web app that helps you transform a raw two-speaker podcast recording into vertical clips ready for short form platforms.

## Getting started

1. Create a virtual environment (optional but recommended) and install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Make sure [ffmpeg](https://ffmpeg.org/) is installed and available on your system path.

3. Create a `.env` file in the project root and add your ElevenLabs key (you can copy `env.example` to `.env`):

   ```env
   ELEVENLABS_API_KEY=your_key_here
   ```

4. Drop a source video in `data/raw/`. The app will use the first file it finds with one of these extensions: `.mp4`, `.mov`, `.mkv`, `.webm`, `.m4v`.

5. Run the Flask development server:

   ```bash
   flask --app app run --debug
   ```

6. Open `http://127.0.0.1:5000/` in your browser.

## Features

- Preview the raw horizontal recording directly in the browser.
- Drag two fixed-format (1.1:1) rectangles to define the speaker crops.
- Confirm the selection to trigger ffmpeg and export two cropped clips (one per speaker) into `data/output/`.

The exported files are available for download from the interface once the process completes.
