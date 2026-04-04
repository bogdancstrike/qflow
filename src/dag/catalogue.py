"""Node catalogue — declarative registry of all processing capabilities.

Each node declares its input/output types, phase, and whether it requires
English text. The planner uses this catalogue to build execution plans
without any node-specific logic.

To add a new node: append one entry to NODE_CATALOGUE below and register
its executor config. No planner or runner changes needed.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class NodeDef:
    """Definition of a single processing node in the DAG."""
    node_id: str
    phase: int  # 1 = ingest, 2 = analysis
    input_type: str
    output_type: str
    requires_en: bool = False

    # Executor configuration — how this node runs
    executor_type: str = "HTTP"  # HTTP or TRANSFORM
    executor_config: dict = field(default_factory=dict)

    # Mock response for DEV_MODE
    mock_response: Optional[dict] = None


# ---------------------------------------------------------------------------
# The full node catalogue — single source of truth
# ---------------------------------------------------------------------------

NODE_CATALOGUE: Dict[str, NodeDef] = {}

_NODES = [
    # Phase 1 — Ingest (normalise any input to text)
    NodeDef(
        node_id="ytdlp_download",
        phase=1,
        input_type="youtube_url",
        output_type="audio_path",
        executor_type="TRANSFORM",
        executor_config={"handler": "ytdlp"},
        mock_response={"audio_path": "/tmp/uploads/youtube_downloaded.mp3"},
    ),
    NodeDef(
        node_id="stt",
        phase=1,
        input_type="audio_path",
        output_type="text",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_STT_URL",
            "path": "/transcribe",
            "body_template": {"file_path": "{audio_path}"},
            "output_field": "text",
            "timeout_seconds": 600,
        },
        mock_response={
            "text": "Der Bundeskanzler hat gestern in Berlin eine wichtige Rede gehalten.",
        },
    ),

    # Phase 2 — Analysis (text -> various outputs)
    NodeDef(
        node_id="lang_detect",
        phase=2,
        input_type="text",
        output_type="lang_meta",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_SERVICE_URL",
            "path": "/detect_language",
            "body_template": {"text": "{text}"},
            "output_field": "language",
            "timeout_seconds": 30,
        },
        mock_response={"language": "ja", "text": "東京で開催された会議で田中太郎氏がソニーの新戦略を発表しました。"},
    ),
    NodeDef(
        node_id="translate",
        phase=2,
        input_type="text",
        output_type="text_en",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_SERVICE_URL",
            "path": "/translate",
            "body_template": {"text": "{text}", "source_language": "{lang}", "target_language": "en"},
            "output_field": "text",
            "timeout_seconds": 60,
            "conditional_skip_on": "lang_is_en",
        },
        mock_response={"text": "At a conference held in Tokyo, Mr. Taro Tanaka announced Sony's new strategy."},
    ),
    NodeDef(
        node_id="summarize",
        phase=2,
        input_type="text",
        output_type="summary",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_SUMMARY_URL",
            "path": "/summarize",
            "body_template": {"text": "{text}"},
            "output_field": "summary",
            "timeout_seconds": 60,
        },
        mock_response={"summary": "A conference was held where new strategies were announced."},
    ),
    NodeDef(
        node_id="iptc",
        phase=2,
        input_type="text",
        output_type="iptc_tags",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_TAXONOMY_URL",
            "path": "/classify",
            "body_template": {"text": "{text}"},
            "output_field": "tags",
            "timeout_seconds": 60,
        },
        mock_response={"tags": ["economy", "business", "technology"]},
    ),
    NodeDef(
        node_id="keyword_extract",
        phase=2,
        input_type="text",
        output_type="keywords",
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_SERVICE_URL",
            "path": "/keywords",
            "body_template": {"text": "{text}"},
            "output_field": "keywords",
            "timeout_seconds": 60,
        },
        mock_response={"keywords": ["conference", "strategy", "technology"]},
    ),
    NodeDef(
        node_id="ner",
        phase=2,
        input_type="text_en",
        output_type="ner_result",
        requires_en=True,
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_NER_URL",
            "path": "/ner",
            "body_template": {"text": "{text_en}"},
            "output_field": "entities",
            "timeout_seconds": 60,
        },
        mock_response={
            "entities": [
                {"text": "Tokyo", "type": "LOCATION", "start": 27, "end": 32},
                {"text": "Taro Tanaka", "type": "PERSON", "start": 38, "end": 49},
                {"text": "Sony", "type": "ORGANIZATION", "start": 60, "end": 64},
            ]
        },
    ),
    NodeDef(
        node_id="sentiment",
        phase=2,
        input_type="text_en",
        output_type="sentiment_result",
        requires_en=True,
        executor_type="HTTP",
        executor_config={
            "method": "POST",
            "url_env": "AI_SENTIMENT_URL",
            "path": "/sentiment",
            "body_template": {"text": "{text_en}"},
            "output_field": "sentiment",
            "timeout_seconds": 60,
        },
        mock_response={"sentiment": "neutral", "score": 0.65},
    ),
]

for _n in _NODES:
    NODE_CATALOGUE[_n.node_id] = _n


# ---------------------------------------------------------------------------
# Lookup helpers (used by the planner — no node-specific logic here)
# ---------------------------------------------------------------------------

# Reverse index: output_type -> NodeDef
_OUTPUT_TO_NODE: Dict[str, NodeDef] = {n.output_type: n for n in NODE_CATALOGUE.values()}

# Reverse index: input_type -> NodeDef (Phase 1 only, for chaining)
_INPUT_TO_PHASE1: Dict[str, NodeDef] = {
    n.input_type: n for n in NODE_CATALOGUE.values() if n.phase == 1
}


def get_node(node_id: str) -> Optional[NodeDef]:
    """Get a node definition by ID."""
    return NODE_CATALOGUE.get(node_id)


def get_node_by_output(output_type: str) -> Optional[NodeDef]:
    """Find the node that produces a given output type."""
    return _OUTPUT_TO_NODE.get(output_type)


def get_phase1_node_for_input(input_type: str) -> Optional[NodeDef]:
    """Find the Phase 1 node that consumes a given input type."""
    return _INPUT_TO_PHASE1.get(input_type)


def get_all_valid_output_types() -> list:
    """Return all output types that the catalogue can produce (Phase 2)."""
    return sorted(
        n.output_type for n in NODE_CATALOGUE.values() if n.phase == 2
    )


def register_node(node: NodeDef):
    """Register a new node at runtime (extensibility)."""
    NODE_CATALOGUE[node.node_id] = node
    _OUTPUT_TO_NODE[node.output_type] = node
    if node.phase == 1:
        _INPUT_TO_PHASE1[node.input_type] = node
