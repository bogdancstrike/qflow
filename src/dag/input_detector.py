"""Input type detection — determines the Phase 1 entry point from a task payload.

Detection rules (evaluated in order):
  1. url field matching YouTube URL patterns -> youtube_url
  2. file_path field with audio/video extension -> audio_path
  3. text field -> text
  4. Anything else -> error
"""

import os
import re

YOUTUBE_PATTERNS = (
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v="),
    re.compile(r"(?:https?://)?youtu\.be/"),
)

AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".avi", ".webm", ".mov", ".ts"})
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class InputDetectionError(ValueError):
    """Raised when the input payload cannot be classified."""
    pass


def detect_input_type(input_data: dict) -> str:
    """Detect the input type from a task payload's input_data dict.

    Returns one of: 'youtube_url', 'audio_path', 'text'.
    Raises InputDetectionError if the input cannot be classified.
    """
    if not isinstance(input_data, dict):
        raise InputDetectionError("input_data must be a JSON object")

    # 1. YouTube URL
    url = input_data.get("url")
    if url and isinstance(url, str):
        for pattern in YOUTUBE_PATTERNS:
            if pattern.search(url):
                return "youtube_url"

    # 2. File path with audio/video extension
    file_path = input_data.get("file_path")
    if file_path and isinstance(file_path, str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in MEDIA_EXTENSIONS:
            return "audio_path"
        raise InputDetectionError(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {sorted(MEDIA_EXTENSIONS)}"
        )

    # 3. Text
    text = input_data.get("text")
    if text and isinstance(text, str):
        return "text"

    raise InputDetectionError(
        "input_data must contain one of: 'text' (string), "
        "'file_path' (audio/video path), or 'url' (YouTube URL)"
    )
