"""yt-dlp executor — downloads and extracts audio from YouTube URLs.

This is a TRANSFORM-type executor that shells out to yt-dlp as a subprocess.
It produces an audio file path (MP3) for the STT node to consume.
"""

import os
import subprocess
import tempfile
import uuid

from framework.commons.logger import logger

from src.config import Config
from src.dag.catalogue import NodeDef

YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT_SEC", "300"))


def execute_ytdlp(node: NodeDef, context: dict) -> dict:
    """Download audio from a YouTube URL using yt-dlp.

    Reads context["youtube_url"] (the URL string or a dict with a "url" field),
    downloads and extracts audio as MP3, and returns a dict with "audio_path".
    """
    url_val = context.get("youtube_url")
    if isinstance(url_val, dict):
        url = url_val.get("url", "")
    else:
        url = str(url_val or "")

    if not url:
        raise ValueError("ytdlp_download: no YouTube URL found in context")

    # DEV_MODE: return mock
    if Config.DEV_MODE and node.mock_response is not None:
        logger.info(f"[YTDLP-MOCK] Returning mock audio path for URL: {url}")
        return node.mock_response

    output_dir = Config.UPLOAD_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"ytdlp_{uuid.uuid4().hex}"
    output_template = os.path.join(output_dir, f"{output_filename}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--output", output_template,
        "--no-playlist",
        "--no-check-certificates",
        url,
    ]

    logger.info(f"[YTDLP] Downloading audio from: {url}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"yt-dlp failed (exit {result.returncode}): {stderr}")

        # Find the output file
        audio_path = os.path.join(output_dir, f"{output_filename}.mp3")
        if not os.path.exists(audio_path):
            # yt-dlp may have used a different extension before converting
            for f in os.listdir(output_dir):
                if f.startswith(output_filename):
                    audio_path = os.path.join(output_dir, f)
                    break

        if not os.path.exists(audio_path):
            raise RuntimeError(
                f"yt-dlp completed but output file not found. "
                f"stdout: {result.stdout[:500]}"
            )

        logger.info(f"[YTDLP] Downloaded audio to: {audio_path}")
        return {"audio_path": audio_path}

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp timed out after {YTDLP_TIMEOUT}s for URL: {url}")
