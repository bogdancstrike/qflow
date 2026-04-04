"""Unit tests for the DAG node catalogue."""

import pytest
from src.dag.catalogue import (
    NODE_CATALOGUE, get_node, get_node_by_output, get_phase1_node_for_input,
    get_all_valid_output_types, register_node, NodeDef,
)


class TestNodeCatalogue:
    """Verify the node catalogue is correctly populated."""

    def test_catalogue_has_nodes(self):
        assert len(NODE_CATALOGUE) >= 9

    def test_phase1_ingest_nodes(self):
        ytdlp = get_node("ytdlp_download")
        assert ytdlp is not None
        assert ytdlp.phase == 1
        assert ytdlp.input_type == "youtube_url"
        assert ytdlp.output_type == "audio_path"

        stt = get_node("stt")
        assert stt is not None
        assert stt.phase == 1
        assert stt.input_type == "audio_path"
        assert stt.output_type == "text"

    def test_phase2_analysis_nodes(self):
        ner = get_node("ner")
        assert ner is not None
        assert ner.phase == 2
        assert ner.requires_en is True
        assert ner.input_type == "text_en"
        assert ner.output_type == "ner_result"

        sentiment = get_node("sentiment")
        assert sentiment is not None
        assert sentiment.requires_en is True

        summarize = get_node("summarize")
        assert summarize is not None
        assert summarize.requires_en is False

    def test_get_node_by_output(self):
        assert get_node_by_output("ner_result").node_id == "ner"
        assert get_node_by_output("sentiment_result").node_id == "sentiment"
        assert get_node_by_output("summary").node_id == "summarize"
        assert get_node_by_output("text").node_id == "stt"
        assert get_node_by_output("nonexistent") is None

    def test_get_phase1_node_for_input(self):
        assert get_phase1_node_for_input("youtube_url").node_id == "ytdlp_download"
        assert get_phase1_node_for_input("audio_path").node_id == "stt"
        assert get_phase1_node_for_input("text") is None  # text is already Phase 2 input

    def test_get_all_valid_output_types(self):
        outputs = get_all_valid_output_types()
        assert isinstance(outputs, list)
        assert len(outputs) >= 5
        assert "ner_result" in outputs
        assert "sentiment_result" in outputs
        assert "summary" in outputs
        assert "iptc_tags" in outputs
        assert "keywords" in outputs

    def test_register_new_node(self):
        ocr_node = NodeDef(
            node_id="ocr_test",
            phase=2,
            input_type="text",
            output_type="ocr_test_result",
            executor_type="HTTP",
            executor_config={"url_env": "AI_OCR_URL", "path": "/ocr"},
            mock_response={"text": "OCR test output"},
        )
        register_node(ocr_node)
        assert get_node("ocr_test") is ocr_node
        assert get_node_by_output("ocr_test_result") is ocr_node
        assert "ocr_test_result" in get_all_valid_output_types()

        # Cleanup
        del NODE_CATALOGUE["ocr_test"]

    def test_all_nodes_have_mock_responses(self):
        """DEV_MODE requires mock responses."""
        for node_id, node in NODE_CATALOGUE.items():
            assert node.mock_response is not None, f"Node '{node_id}' missing mock_response"

    def test_all_nodes_have_executor_config(self):
        for node_id, node in NODE_CATALOGUE.items():
            assert node.executor_type in ("HTTP", "TRANSFORM"), \
                f"Node '{node_id}' has invalid executor_type: {node.executor_type}"
