"""Template and flow definition loader.

Loads:
- Primitive definitions (DSL schema/examples) from templates/ directory
- Flow definitions (complete pipelines) from flows/ directory
"""

import json
from pathlib import Path

from framework.commons.logger import logger

from src.templating.validator import validate_flow_definition


def load_json_file(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def load_primitives(templates_dir: str) -> dict:
    """Load primitive definitions (DSL building blocks) from a directory.

    These are schema + example definitions for each task type
    (HTTP, SWITCH, FORK_JOIN, etc.), not executable task configs.

    Returns dict of {primitive_name: definition_dict}.
    """
    primitives = {}
    templates_path = Path(templates_dir)

    if not templates_path.exists():
        logger.warning(f"[LOADER] Templates directory not found: {templates_dir}")
        return primitives

    for json_file in sorted(templates_path.glob("*.json")):
        try:
            definition = load_json_file(str(json_file))
            name = definition.get("primitive", json_file.stem)
            primitives[name] = definition
            logger.debug(f"[LOADER] Loaded primitive: {name} from {json_file.name}")
        except Exception as e:
            logger.error(f"[LOADER] Failed to load primitive {json_file.name}: {e}")

    logger.info(f"[LOADER] Loaded {len(primitives)} primitives from {templates_dir}")
    return primitives


def load_flows(flows_dir: str) -> dict:
    """Load all flow definitions from a directory.

    Returns dict of {flow_id: flow_dict}.
    """
    flows = {}
    flows_path = Path(flows_dir)

    if not flows_path.exists():
        logger.warning(f"[LOADER] Flows directory not found: {flows_dir}")
        return flows

    for json_file in sorted(flows_path.glob("*.json")):
        try:
            flow = load_json_file(str(json_file))
            validate_flow_definition(flow)
            flow_id = flow.get("flow_id", json_file.stem)
            flows[flow_id] = flow
            logger.debug(f"[LOADER] Loaded flow: {flow_id} from {json_file.name}")
        except Exception as e:
            logger.error(f"[LOADER] Failed to load flow {json_file.name}: {e}")

    logger.info(f"[LOADER] Loaded {len(flows)} flows from {flows_dir}")
    return flows
