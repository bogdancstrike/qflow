"""Integration tests — end-to-end pipeline execution in DEV_MODE.

Each test represents a TASK: input -> desired_output.
The FLOW is the sequence of primitives (HTTP, SWITCH, SET_VARIABLE, LOG, etc.)
that the executor resolves and runs to produce the output.

Example:
    Task:  input=test.mp4, desired_output=ner
    Flow:  flow_video_to_ner
    Chain: LOG -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH(language)
                -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
"""

import os
import pytest

os.environ["DEV_MODE"] = "true"

from src.core.context import ExecutionContext
from src.core.executor import execute_flow
from src.core.resolver import resolve_flow
from src.templating.registry import init_registry, get_flow


@pytest.fixture(scope="module", autouse=True)
def setup_registry():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    init_registry(base_dir)


def _make_env():
    return {
        "AI_STT_URL": "http://stt-service:8001",
        "AI_STT_TOKEN": "dev-token",
        "AI_NER_URL": "http://ner-service:8002",
        "AI_TRANSLATE_URL": "http://translate-service:8003",
        "AI_LANGDETECT_URL": "http://langdetect-service:8004",
        "AI_SENTIMENT_URL": "http://sentiment-service:8005",
        "AI_SUMMARY_URL": "http://summary-service:8006",
        "AI_TAXONOMY_URL": "http://taxonomy-service:8007",
        "AI_SERVICE_URL": "http://ai-service:8000",
    }


# Primitive type labels for the report
_PRIMITIVE_LABELS = {
    "LOG": "LOG",
    "HTTP": "HTTP",
    "SWITCH": "SWITCH",
    "SET_VARIABLE": "SET_VAR",
    "TRANSFORM": "TRANSFORM",
    "FORK_JOIN": "FORK_JOIN",
    "DO_WHILE": "DO_WHILE",
    "SUB_WORKFLOW": "SUB_FLOW",
    "TERMINATE": "TERMINATE",
    "WAIT": "WAIT",
}


def _primitive_label(task_def):
    """Build a human-readable label for a primitive step.
    HTTP steps show the service name: HTTP(stt), HTTP(ner), etc.
    """
    ptype = task_def.get("type", "?")
    label = _PRIMITIVE_LABELS.get(ptype, ptype)
    if ptype == "HTTP":
        ref = task_def.get("task_ref", "")
        label = f"HTTP({ref})"
    return label


def _build_chain(flow):
    """Build the primitive chain string from a flow definition.
    Flattens SWITCH branches into the chain.
    """
    parts = []
    for task in flow.get("tasks", []):
        ptype = task.get("type", "?")
        if ptype == "SWITCH":
            parts.append(f"SWITCH({task.get('task_ref', '?')})")
            # Show default_case branch (most common path in mock)
            for sub in task.get("default_case", []):
                parts.append(_primitive_label(sub))
        else:
            parts.append(_primitive_label(task))
    return " -> ".join(parts)


def _build_step_type_map(tasks):
    """Build {task_ref: type} map from flow tasks, including SWITCH branches."""
    m = {}
    for t in tasks:
        m[t["task_ref"]] = t["type"]
        if t["type"] == "SWITCH":
            for case_tasks in t.get("decision_cases", {}).values():
                for sub in case_tasks:
                    m[sub["task_ref"]] = sub["type"]
            for sub in t.get("default_case", []):
                m[sub["task_ref"]] = sub["type"]
    return m


def _run_task(input_type, input_data, desired_output):
    """Resolve and execute a complete task. Returns (result, context, flow_id)."""
    flow_id = resolve_flow(input_type, desired_output)
    flow = get_flow(flow_id)
    assert flow is not None, f"Flow {flow_id} not found in registry"

    ctx = ExecutionContext(input_data, _make_env())
    result = execute_flow(flow, ctx)

    # --- Task execution report ---
    chain = _build_chain(flow)
    type_map = _build_step_type_map(flow.get("tasks", []))
    total_ms = sum(s.get("duration_ms", 0) for s in ctx.steps.values())

    step_lines = []
    for ref, step_data in ctx.steps.items():
        status = step_data.get("status", "?")
        dur = step_data.get("duration_ms", 0)
        ptype = type_map.get(ref, "?")
        if ptype == "HTTP":
            step_lines.append(f"    HTTP({ref}): {status} ({dur}ms)")
        elif ptype == "SET_VARIABLE":
            step_lines.append(f"    SET_VAR({ref}): {status}")
        elif ptype == "LOG":
            step_lines.append(f"    LOG({ref}): {status}")
        else:
            step_lines.append(f"    {ptype}({ref}): {status} ({dur}ms)")

    print(f"\n{'='*70}")
    print(f"  TASK:  {input_type} -> {desired_output}")
    print(f"  FLOW:  {flow_id}")
    print(f"  CHAIN: {chain}")
    print(f"  STEPS: {len(ctx.steps)} primitives executed ({total_ms}ms total)")
    for line in step_lines:
        print(line)
    if ctx.variables:
        print(f"  VARS:  {ctx.variables}")
    print(f"  RESULT: {result}")
    print(f"{'='*70}")

    return result, ctx, flow_id


# ============================================================
# File upload tasks (audio/video -> AI output)
# ============================================================

class TestFileUploadTasks:
    """Tasks: input=file_upload (e.g. test.mp4) -> various outputs.
    All file_upload flows start with STT(HTTP) to transcribe audio.
    """

    def test_file_to_stt(self):
        """Task: test.mp4 -> STT
        Flow: LOG -> HTTP(stt) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "stt"
        )
        assert flow_id == "flow_video_to_stt"
        assert result is not None
        assert "text" in result
        assert "stt" in ctx.steps
        assert ctx.steps["stt"]["status"] == "SUCCESS"

    def test_file_to_ner(self):
        """Task: test.mp4 -> NER
        Flow: LOG -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH(language)
              -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "ner"
        )
        assert flow_id == "flow_video_to_ner"
        assert result is not None
        assert "entities" in result
        assert len(result["entities"]) > 0
        # Verify the full primitive chain executed
        assert "stt" in ctx.steps
        assert "language_detect" in ctx.steps
        assert "check_language" in ctx.steps
        assert "ner" in ctx.steps
        assert result["language_detected"] == "de"

    def test_file_to_sentiment(self):
        """Task: test.mp4 -> Sentiment
        Flow: LOG -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH(language)
              -> HTTP(translate) -> SET_VAR -> HTTP(sentiment) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "sentiment"
        )
        assert flow_id == "flow_video_to_sentiment"
        assert result is not None
        assert "sentiment" in result
        assert "score" in result
        assert "stt" in ctx.steps
        assert "sentiment" in ctx.steps

    def test_file_to_summary(self):
        """Task: test.mp4 -> Summary
        Flow: LOG -> HTTP(stt) -> HTTP(lang-detect) -> SWITCH(language)
              -> HTTP(translate) -> SET_VAR -> HTTP(summary) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "file_upload", {"file_path": "/tmp/test.mp4"}, "summary"
        )
        assert flow_id == "flow_video_to_summary"
        assert result is not None
        assert "summary" in result
        assert "stt" in ctx.steps
        assert "summary" in ctx.steps


# ============================================================
# Text input tasks (raw text -> AI output)
# ============================================================

class TestTextTasks:
    """Tasks: input=text -> various outputs.
    Text flows skip STT and start with language detection.
    """

    def test_text_to_ner(self):
        """Task: "John Smith lives in New York" -> NER
        Flow: LOG -> HTTP(lang-detect) -> SWITCH(language)
              -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "text", {"text": "John Smith lives in New York and works at Acme Corp."}, "ner"
        )
        assert flow_id == "flow_text_to_ner"
        assert result is not None
        assert "entities" in result
        assert len(result["entities"]) > 0
        assert "language_detect" in ctx.steps
        assert "ner" in ctx.steps
        # Verify entity types are present
        entity_types = {e["type"] for e in result["entities"]}
        assert "PERSON" in entity_types or "LOCATION" in entity_types

    def test_text_to_sentiment(self):
        """Task: "I love this product!" -> Sentiment
        Flow: LOG -> HTTP(lang-detect) -> SWITCH -> HTTP(translate) -> SET_VAR -> HTTP(sentiment) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "text", {"text": "I love this product! It's amazing."}, "sentiment"
        )
        assert flow_id == "flow_text_to_sentiment"
        assert result is not None
        assert "sentiment" in result
        assert "score" in result
        assert "language_detect" in ctx.steps
        assert "sentiment" in ctx.steps

    def test_text_to_summary(self):
        """Task: long article -> Summary
        Flow: LOG -> HTTP(lang-detect) -> SWITCH -> HTTP(translate) -> SET_VAR -> HTTP(summary) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "text", {"text": "A long article about technology and innovation in the modern era..."}, "summary"
        )
        assert flow_id == "flow_text_to_summary"
        assert result is not None
        assert "summary" in result
        assert "language_detect" in ctx.steps
        assert "summary" in ctx.steps


# ============================================================
# YouTube link tasks (youtube URL -> AI output)
# ============================================================

class TestYouTubeTasks:
    """Tasks: input=youtube_link -> various outputs.
    YouTube flows start with download(HTTP) + STT(HTTP) before processing.
    """

    def test_youtube_to_stt(self):
        """Task: youtube.com/watch?v=test -> STT
        Flow: LOG -> HTTP(download) -> HTTP(stt) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "youtube_link", {"youtube_url": "https://youtube.com/watch?v=test123"}, "stt"
        )
        assert flow_id == "flow_youtube_to_stt"
        assert result is not None
        assert "text" in result
        assert "youtube_download" in ctx.steps
        assert "stt" in ctx.steps

    def test_youtube_to_ner(self):
        """Task: youtube.com/watch?v=test -> NER
        Flow: LOG -> HTTP(download) -> HTTP(stt) -> HTTP(lang-detect)
              -> SWITCH -> HTTP(translate) -> SET_VAR -> HTTP(ner) -> LOG
        """
        result, ctx, flow_id = _run_task(
            "youtube_link", {"youtube_url": "https://youtube.com/watch?v=test123"}, "ner"
        )
        assert flow_id == "flow_youtube_to_ner"
        assert result is not None
        assert "entities" in result
        assert len(result["entities"]) > 0
        assert "youtube_download" in ctx.steps
        assert "stt" in ctx.steps
        assert "language_detect" in ctx.steps
        assert "ner" in ctx.steps
