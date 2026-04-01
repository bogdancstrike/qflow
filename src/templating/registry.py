"""In-memory registry for primitive definitions and flow definitions.

Loaded once at startup, provides fast lookup for the executor.

- Primitives: DSL building block definitions (HTTP, SWITCH, etc.) with schema + examples
- Flows: Complete pipeline definitions that compose primitives into executable workflows
"""

import os

from framework.commons.logger import logger

from src.templating.loader import load_primitives, load_flows

_primitives = {}
_flows = {}
_initialized = False


def init_registry(base_dir: str = None):
    """Initialize the registry by loading primitives and flows from disk."""
    global _primitives, _flows, _initialized

    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "..")

    templates_dir = os.path.join(base_dir, "src", "templating", "templates")
    flows_dir = os.path.join(base_dir, "src", "templating", "flows")

    _primitives = load_primitives(templates_dir)
    _flows = load_flows(flows_dir)
    _initialized = True

    logger.info(f"[REGISTRY] Initialized: {len(_primitives)} primitives, {len(_flows)} flows")


def get_primitive(name: str) -> dict:
    """Get a primitive definition by name (HTTP, SWITCH, etc.)."""
    if not _initialized:
        init_registry()
    return _primitives.get(name)


def get_flow(flow_id: str) -> dict:
    """Get a flow definition by ID."""
    if not _initialized:
        init_registry()
    return _flows.get(flow_id)


def list_primitives() -> list:
    """List all registered primitive names."""
    if not _initialized:
        init_registry()
    return list(_primitives.keys())


def list_flows() -> list:
    """List all registered flow IDs."""
    if not _initialized:
        init_registry()
    return list(_flows.keys())


def register_flow(flow_id: str, flow: dict):
    """Register a new flow definition at runtime."""
    _flows[flow_id] = flow
