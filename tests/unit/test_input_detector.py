"""Unit tests for DAG input type detection."""

import pytest
from src.dag.input_detector import detect_input_type, InputDetectionError


class TestInputDetector:

    def test_detect_text(self):
        assert detect_input_type({"text": "Hello world"}) == "text"

    def test_detect_youtube_url_full(self):
        assert detect_input_type({"url": "https://www.youtube.com/watch?v=abc123"}) == "youtube_url"

    def test_detect_youtube_url_short(self):
        assert detect_input_type({"url": "https://youtu.be/abc123"}) == "youtube_url"

    def test_detect_audio_mp3(self):
        assert detect_input_type({"file_path": "/tmp/audio.mp3"}) == "audio_path"

    def test_detect_audio_wav(self):
        assert detect_input_type({"file_path": "/tmp/audio.wav"}) == "audio_path"

    def test_detect_video_mp4(self):
        assert detect_input_type({"file_path": "/tmp/video.mp4"}) == "audio_path"

    def test_detect_video_mkv(self):
        assert detect_input_type({"file_path": "/tmp/video.mkv"}) == "audio_path"

    def test_unsupported_extension_raises(self):
        with pytest.raises(InputDetectionError, match="Unsupported file extension"):
            detect_input_type({"file_path": "/tmp/doc.pdf"})

    def test_empty_dict_raises(self):
        with pytest.raises(InputDetectionError, match="must contain one of"):
            detect_input_type({})

    def test_non_dict_raises(self):
        with pytest.raises(InputDetectionError, match="must be a JSON object"):
            detect_input_type("not a dict")

    def test_unknown_fields_raises(self):
        with pytest.raises(InputDetectionError, match="must contain one of"):
            detect_input_type({"unknown": "value"})

    def test_non_youtube_url_not_detected(self):
        """Non-YouTube URLs should not match youtube_url type."""
        with pytest.raises(InputDetectionError):
            detect_input_type({"url": "https://example.com/video.mp4"})

    def test_priority_url_over_text(self):
        """URL takes priority over text field."""
        result = detect_input_type({
            "url": "https://youtube.com/watch?v=abc",
            "text": "Hello world",
        })
        assert result == "youtube_url"

    def test_priority_file_path_over_text(self):
        """file_path takes priority over text field."""
        result = detect_input_type({
            "file_path": "/tmp/audio.mp3",
            "text": "Hello world",
        })
        assert result == "audio_path"
