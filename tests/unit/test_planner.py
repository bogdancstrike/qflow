"""Unit tests for the DAG planner."""

import pytest
from src.dag.planner import build_plan, PlanningError, ExecutionPlan, ExecutionBranch


class TestBuildPlan:
    """Verify plan construction for all input/output combinations."""

    # --- Text input ---

    def test_text_to_ner(self):
        plan = build_plan({"text": "Hello world"}, ["ner_result"])
        assert plan.input_type == "text"
        assert len(plan.ingest_steps) == 0  # text needs no ingestion
        assert len(plan.branches) == 1
        branch = plan.branches[0]
        assert branch.output_type == "ner_result"
        # NER requires EN: lang_detect -> translate -> ner
        step_ids = [s.node_id for s in branch.steps]
        assert step_ids == ["lang_detect", "translate", "ner"]

    def test_text_to_sentiment(self):
        plan = build_plan({"text": "Great product!"}, ["sentiment_result"])
        assert plan.input_type == "text"
        assert len(plan.ingest_steps) == 0
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["lang_detect", "translate", "sentiment"]

    def test_text_to_summary(self):
        plan = build_plan({"text": "Long article text"}, ["summary"])
        assert plan.input_type == "text"
        assert len(plan.ingest_steps) == 0
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["summarize"]  # summary does NOT require EN

    def test_text_to_iptc(self):
        plan = build_plan({"text": "News article"}, ["iptc_tags"])
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["iptc"]

    def test_text_to_keywords(self):
        plan = build_plan({"text": "Tech article"}, ["keywords"])
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["keyword_extract"]

    # --- File input ---

    def test_file_to_ner(self):
        plan = build_plan({"file_path": "/tmp/test.mp4"}, ["ner_result"])
        assert plan.input_type == "audio_path"
        assert len(plan.ingest_steps) == 1  # stt
        assert plan.ingest_steps[0].node_id == "stt"
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["lang_detect", "translate", "ner"]

    def test_file_to_summary(self):
        plan = build_plan({"file_path": "/tmp/audio.wav"}, ["summary"])
        assert plan.input_type == "audio_path"
        assert len(plan.ingest_steps) == 1
        step_ids = [s.node_id for s in plan.branches[0].steps]
        assert step_ids == ["summarize"]

    # --- YouTube input ---

    def test_youtube_to_ner(self):
        plan = build_plan({"url": "https://youtube.com/watch?v=abc"}, ["ner_result"])
        assert plan.input_type == "youtube_url"
        assert len(plan.ingest_steps) == 2  # ytdlp_download -> stt
        ingest_ids = [s.node_id for s in plan.ingest_steps]
        assert ingest_ids == ["ytdlp_download", "stt"]

    def test_youtube_to_summary(self):
        plan = build_plan({"url": "https://youtu.be/abc"}, ["summary"])
        assert plan.input_type == "youtube_url"
        assert len(plan.ingest_steps) == 2

    # --- Multi-output ---

    def test_multi_output(self):
        plan = build_plan(
            {"text": "Hello world"},
            ["ner_result", "sentiment_result", "summary"],
        )
        assert len(plan.branches) == 3
        output_types = {b.output_type for b in plan.branches}
        assert output_types == {"ner_result", "sentiment_result", "summary"}

    def test_all_outputs(self):
        outputs = ["ner_result", "sentiment_result", "summary", "iptc_tags", "keywords", "lang_meta", "text_en"]
        plan = build_plan({"text": "Test all outputs"}, outputs)
        assert len(plan.branches) == len(outputs)

    # --- Serialization ---

    def test_plan_to_dict(self):
        plan = build_plan({"url": "https://youtube.com/watch?v=abc"}, ["ner_result"])
        d = plan.to_dict()
        assert d["input_type"] == "youtube_url"
        assert d["ingest_steps"] == ["ytdlp_download", "stt"]
        assert len(d["branches"]) == 1
        assert d["branches"][0]["output_type"] == "ner_result"
        assert d["branches"][0]["steps"] == ["lang_detect", "translate", "ner"]

    # --- Error cases ---

    def test_empty_outputs_raises(self):
        with pytest.raises(PlanningError, match="At least one output"):
            build_plan({"text": "hello"}, [])

    def test_unknown_output_raises(self):
        with pytest.raises(PlanningError, match="Unknown output"):
            build_plan({"text": "hello"}, ["nonexistent_output"])

    def test_unclassifiable_input_raises(self):
        with pytest.raises(PlanningError):
            build_plan({"unknown_field": "value"}, ["ner_result"])

    def test_unsupported_file_extension_raises(self):
        with pytest.raises(PlanningError):
            build_plan({"file_path": "/tmp/doc.pdf"}, ["summary"])
