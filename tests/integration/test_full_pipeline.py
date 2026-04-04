"""Integration tests — end-to-end DAG pipeline execution in DEV_MODE.

Each test builds an execution plan via the planner, executes it via the DAG runner,
and verifies the output. All AI service calls are mocked (DEV_MODE=true).

Example:
    Input:  {"text": "John Smith lives in Berlin"}
    Outputs: ["ner_result"]
    Plan:   ingest=[] -> branches=[lang_detect -> translate -> ner]
"""

import os
import time
import pytest

os.environ["DEV_MODE"] = "true"

from src.dag.planner import build_plan
from src.dag.runner import run_plan


REPORT_FILE = os.path.join(os.path.dirname(__file__), "../../reports/integration_pipeline.txt")


def _write_report(test_name, lines):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "a") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"  TEST: {test_name}\n")
        f.write(f"  TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for line in lines:
            f.write(f"  {line}\n")
        f.write(f"{'='*70}\n")


def _run_pipeline(input_data, outputs):
    """Build plan and execute it. Returns (result, plan, elapsed_ms)."""
    plan = build_plan(input_data, outputs)

    context = dict(input_data)
    # Set up context for input type routing
    if plan.input_type == "youtube_url" and "url" in input_data:
        context["youtube_url"] = input_data["url"]
    elif plan.input_type == "audio_path" and "file_path" in input_data:
        context["audio_path"] = input_data["file_path"]

    start = time.time()
    result = run_plan(plan, context)
    elapsed_ms = int((time.time() - start) * 1000)

    return result, plan, elapsed_ms


# ============================================================
# Text input -> various outputs
# ============================================================

class TestTextPipeline:

    def test_text_to_ner(self):
        result, plan, ms = _run_pipeline(
            {"text": "John Smith lives in Berlin and works at Acme Corp."},
            ["ner_result"],
        )
        assert "ner_result" in result
        assert "entities" in result["ner_result"]
        assert len(result["ner_result"]["entities"]) > 0

        _write_report("test_text_to_ner", [
            f"Input: text -> ner_result",
            f"Plan: ingest={[n.node_id for n in plan.ingest_steps]}, "
            f"branches={[b.output_type for b in plan.branches]}",
            f"Duration: {ms}ms",
            f"Result keys: {list(result.keys())}",
            f"Entities: {len(result['ner_result']['entities'])}",
            "PASS",
        ])

    def test_text_to_sentiment(self):
        result, plan, ms = _run_pipeline(
            {"text": "I absolutely love this product! It's amazing."},
            ["sentiment_result"],
        )
        assert "sentiment_result" in result
        assert "sentiment" in result["sentiment_result"]

        _write_report("test_text_to_sentiment", [
            f"Duration: {ms}ms",
            f"Result: {result['sentiment_result']}",
            "PASS",
        ])

    def test_text_to_summary(self):
        result, plan, ms = _run_pipeline(
            {"text": "A long article about technology and innovation."},
            ["summary"],
        )
        assert "summary" in result
        assert "summary" in result["summary"]

        _write_report("test_text_to_summary", [
            f"Duration: {ms}ms",
            f"Result: {result['summary']}",
            "PASS",
        ])

    def test_text_to_iptc(self):
        result, plan, ms = _run_pipeline(
            {"text": "Government announces new economic policies."},
            ["iptc_tags"],
        )
        assert "iptc_tags" in result
        assert "tags" in result["iptc_tags"]

        _write_report("test_text_to_iptc", [
            f"Duration: {ms}ms",
            f"Result: {result['iptc_tags']}",
            "PASS",
        ])

    def test_text_to_keywords(self):
        result, plan, ms = _run_pipeline(
            {"text": "AI conference in Tokyo discusses new breakthroughs."},
            ["keywords"],
        )
        assert "keywords" in result
        assert "keywords" in result["keywords"]

        _write_report("test_text_to_keywords", [
            f"Duration: {ms}ms",
            f"Result: {result['keywords']}",
            "PASS",
        ])

    def test_text_to_lang_meta(self):
        result, plan, ms = _run_pipeline(
            {"text": "Bonjour le monde."},
            ["lang_meta"],
        )
        assert "lang_meta" in result
        assert "language" in result["lang_meta"]

        _write_report("test_text_to_lang_meta", [
            f"Duration: {ms}ms",
            f"Result: {result['lang_meta']}",
            "PASS",
        ])

    def test_text_multi_output(self):
        """Test parallel branch execution: NER + Sentiment + Summary."""
        result, plan, ms = _run_pipeline(
            {"text": "John Smith loves AI technology."},
            ["ner_result", "sentiment_result", "summary"],
        )
        assert "ner_result" in result
        assert "sentiment_result" in result
        assert "summary" in result
        assert len(plan.branches) == 3

        _write_report("test_text_multi_output", [
            f"Outputs: {list(result.keys())}",
            f"Branches: {len(plan.branches)}",
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_text_all_outputs(self):
        """Test all outputs at once."""
        all_outputs = ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords", "lang_meta", "text_en"]
        result, plan, ms = _run_pipeline(
            {"text": "Comprehensive test of all analysis outputs."},
            all_outputs,
        )
        for out in all_outputs:
            assert out in result, f"Missing output: {out}"

        _write_report("test_text_all_outputs", [
            f"Outputs requested: {len(all_outputs)}",
            f"Outputs received: {len(result)}",
            f"Duration: {ms}ms",
            "PASS",
        ])


# ============================================================
# File input -> various outputs
# ============================================================

class TestFilePipeline:

    def test_file_to_ner(self):
        result, plan, ms = _run_pipeline(
            {"file_path": "/tmp/test.mp4"},
            ["ner_result"],
        )
        assert plan.input_type == "audio_path"
        assert len(plan.ingest_steps) == 1  # stt
        assert "ner_result" in result

        _write_report("test_file_to_ner", [
            f"Ingest: {[n.node_id for n in plan.ingest_steps]}",
            f"Duration: {ms}ms",
            f"NER entities: {len(result['ner_result'].get('entities', []))}",
            "PASS",
        ])

    def test_file_to_sentiment(self):
        result, plan, ms = _run_pipeline(
            {"file_path": "/tmp/audio.wav"},
            ["sentiment_result"],
        )
        assert "sentiment_result" in result

        _write_report("test_file_to_sentiment", [
            f"Duration: {ms}ms",
            f"Result: {result['sentiment_result']}",
            "PASS",
        ])

    def test_file_to_summary(self):
        result, plan, ms = _run_pipeline(
            {"file_path": "/tmp/audio.mp3"},
            ["summary"],
        )
        assert "summary" in result

        _write_report("test_file_to_summary", [
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_file_multi_output(self):
        result, plan, ms = _run_pipeline(
            {"file_path": "/tmp/test.mp4"},
            ["ner_result", "summary", "iptc_tags"],
        )
        assert len(result) == 3
        assert len(plan.ingest_steps) == 1

        _write_report("test_file_multi_output", [
            f"Outputs: {list(result.keys())}",
            f"Duration: {ms}ms",
            "PASS",
        ])


# ============================================================
# YouTube input -> various outputs
# ============================================================

class TestYouTubePipeline:

    def test_youtube_to_ner(self):
        result, plan, ms = _run_pipeline(
            {"url": "https://youtube.com/watch?v=test123"},
            ["ner_result"],
        )
        assert plan.input_type == "youtube_url"
        assert len(plan.ingest_steps) == 2  # ytdlp_download -> stt
        assert "ner_result" in result

        _write_report("test_youtube_to_ner", [
            f"Ingest: {[n.node_id for n in plan.ingest_steps]}",
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_youtube_to_sentiment(self):
        result, plan, ms = _run_pipeline(
            {"url": "https://youtu.be/abc456"},
            ["sentiment_result"],
        )
        assert "sentiment_result" in result

        _write_report("test_youtube_to_sentiment", [
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_youtube_to_summary(self):
        result, plan, ms = _run_pipeline(
            {"url": "https://youtube.com/watch?v=test"},
            ["summary"],
        )
        assert "summary" in result

        _write_report("test_youtube_to_summary", [
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_youtube_multi_output(self):
        result, plan, ms = _run_pipeline(
            {"url": "https://youtube.com/watch?v=multi"},
            ["ner_result", "sentiment_result", "summary", "keywords"],
        )
        assert len(result) == 4
        assert len(plan.ingest_steps) == 2

        _write_report("test_youtube_multi_output", [
            f"Outputs: {list(result.keys())}",
            f"Ingest: {[n.node_id for n in plan.ingest_steps]}",
            f"Branches: {len(plan.branches)}",
            f"Duration: {ms}ms",
            "PASS",
        ])

    def test_youtube_all_outputs(self):
        all_outputs = ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords"]
        result, plan, ms = _run_pipeline(
            {"url": "https://youtube.com/watch?v=all"},
            all_outputs,
        )
        for out in all_outputs:
            assert out in result

        _write_report("test_youtube_all_outputs", [
            f"Outputs: {len(result)} / {len(all_outputs)} requested",
            f"Duration: {ms}ms",
            "PASS",
        ])
