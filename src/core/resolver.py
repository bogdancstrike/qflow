"""Flow strategy resolver — maps (input_type, desired_output) to a flow definition."""

from framework.commons.logger import logger


# Strategy registry: (input_type, desired_output) -> flow_id
FLOW_STRATEGIES = {
    # File upload (audio/video)
    ("file_upload", "stt"): "flow_video_to_stt",
    ("file_upload", "ner"): "flow_video_to_ner",
    ("file_upload", "sentiment"): "flow_video_to_sentiment",
    ("file_upload", "summary"): "flow_video_to_summary",
    ("file_upload", "taxonomy"): "flow_video_to_taxonomy",
    ("file_upload", "language_detect"): "flow_video_to_language_detect",
    ("file_upload", "translate"): "flow_video_to_translate",

    # YouTube link
    ("youtube_link", "stt"): "flow_youtube_to_stt",
    ("youtube_link", "ner"): "flow_youtube_to_ner",
    ("youtube_link", "sentiment"): "flow_youtube_to_sentiment",
    ("youtube_link", "summary"): "flow_youtube_to_summary",
    ("youtube_link", "taxonomy"): "flow_youtube_to_taxonomy",
    ("youtube_link", "language_detect"): "flow_youtube_to_language_detect",
    ("youtube_link", "translate"): "flow_youtube_to_translate",

    # Text input
    ("text", "ner"): "flow_text_to_ner",
    ("text", "sentiment"): "flow_text_to_sentiment",
    ("text", "summary"): "flow_text_to_summary",
    ("text", "taxonomy"): "flow_text_to_taxonomy",
    ("text", "language_detect"): "flow_text_to_language_detect",
    ("text", "translate"): "flow_text_to_translate",
}

# Valid input types per desired output — for input validation
VALID_INPUT_TYPES = {}
for (input_type, output), flow_id in FLOW_STRATEGIES.items():
    VALID_INPUT_TYPES.setdefault(output, set()).add(input_type)


def resolve_flow(input_type: str, desired_output: str) -> str:
    """Resolve a (input_type, desired_output) pair to a flow_id.

    Returns the flow_id string, or raises ValueError if no matching strategy.
    """
    flow_id = FLOW_STRATEGIES.get((input_type, desired_output))
    if flow_id is None:
        raise ValueError(
            f"No flow strategy for input_type='{input_type}', "
            f"desired_output='{desired_output}'"
        )
    logger.info(f"[RESOLVER] ({input_type}, {desired_output}) -> {flow_id}")
    return flow_id


def is_valid_combination(input_type: str, desired_output: str) -> bool:
    return (input_type, desired_output) in FLOW_STRATEGIES


def get_valid_outputs():
    """Return all supported desired_output values."""
    return sorted(set(o for (_, o) in FLOW_STRATEGIES.keys()))


def get_valid_input_types_for_output(desired_output: str):
    """Return valid input_types for a given desired_output."""
    return sorted(VALID_INPUT_TYPES.get(desired_output, set()))


def register_flow_strategy(input_type: str, desired_output: str, flow_id: str):
    """Register a new flow strategy at runtime."""
    FLOW_STRATEGIES[(input_type, desired_output)] = flow_id
    VALID_INPUT_TYPES.setdefault(desired_output, set()).add(input_type)
    logger.info(f"[RESOLVER] Registered: ({input_type}, {desired_output}) -> {flow_id}")
