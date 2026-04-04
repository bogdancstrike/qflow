"""Execution plan builder — computes the DAG plan from input + requested outputs.

The planner is entirely data-driven: it reads the node catalogue and builds
an ExecutionPlan without any node-specific logic. Adding a new node requires
only a catalogue entry — no planner changes.

An ExecutionPlan has two parts:
  1. ingest_steps  — ordered Phase 1 nodes to normalise input -> text (shared)
  2. branches      — one per requested output, each an ordered list of Phase 2 nodes
"""

from dataclasses import dataclass, field
from typing import List, Optional

from framework.commons.logger import logger

from src.dag.catalogue import (
    NodeDef,
    get_node,
    get_node_by_output,
    get_phase1_node_for_input,
    get_all_valid_output_types,
)
from src.dag.input_detector import detect_input_type, InputDetectionError


class PlanningError(ValueError):
    """Raised when a valid execution plan cannot be built."""
    pass


@dataclass
class ExecutionBranch:
    """A single output branch — an ordered list of Phase 2 nodes to execute."""
    output_type: str
    steps: List[NodeDef] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task."""
    input_type: str
    ingest_steps: List[NodeDef] = field(default_factory=list)
    branches: List[ExecutionBranch] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialisable representation for logging/storage."""
        return {
            "input_type": self.input_type,
            "ingest_steps": [n.node_id for n in self.ingest_steps],
            "branches": [
                {
                    "output_type": b.output_type,
                    "steps": [n.node_id for n in b.steps],
                }
                for b in self.branches
            ],
        }


def build_plan(input_data: dict, outputs: List[str]) -> ExecutionPlan:
    """Build an execution plan from a task payload.

    Args:
        input_data: The task's input_data dict (must contain text, file_path, or url).
        outputs: List of requested output type strings.

    Returns:
        An ExecutionPlan ready for the DAG runner.

    Raises:
        PlanningError: If the plan cannot be built (bad input, unknown output, etc.).
    """
    # Validate outputs
    if not outputs:
        raise PlanningError("At least one output type is required")

    valid_outputs = get_all_valid_output_types()
    unknown = [o for o in outputs if o not in valid_outputs]
    if unknown:
        raise PlanningError(
            f"Unknown output type(s): {unknown}. Valid: {valid_outputs}"
        )

    # Detect input type
    try:
        input_type = detect_input_type(input_data)
    except InputDetectionError as e:
        raise PlanningError(str(e))

    # Build Phase 1 ingest chain: walk from input_type -> text
    ingest_steps = _build_ingest_chain(input_type)

    # Build Phase 2 branches
    branches = []
    for output in outputs:
        branch = _build_branch(output)
        branches.append(branch)

    plan = ExecutionPlan(
        input_type=input_type,
        ingest_steps=ingest_steps,
        branches=branches,
    )

    logger.info(f"[PLANNER] Built plan: {plan.to_dict()}")
    return plan


def _build_ingest_chain(input_type: str) -> List[NodeDef]:
    """Build the Phase 1 chain from detected input_type to 'text'.

    Walks the catalogue graph: input_type -> node -> output_type -> next node -> ...
    until output_type == 'text'.
    """
    if input_type == "text":
        return []

    chain = []
    current_type = input_type
    visited = set()

    while current_type != "text":
        if current_type in visited:
            raise PlanningError(
                f"Cycle detected in ingest chain at type '{current_type}'"
            )
        visited.add(current_type)

        node = get_phase1_node_for_input(current_type)
        if node is None:
            raise PlanningError(
                f"No Phase 1 node found to process input type '{current_type}'"
            )
        chain.append(node)
        current_type = node.output_type

    return chain


def _build_branch(output_type: str) -> ExecutionBranch:
    """Build a single Phase 2 branch for a requested output.

    If the target node requires English text, prepend lang_detect + translate.
    """
    target_node = get_node_by_output(output_type)
    if target_node is None:
        raise PlanningError(f"No node produces output type '{output_type}'")

    steps = []

    if target_node.requires_en:
        # Inject EN preparation: lang_detect -> translate
        lang_detect = get_node("lang_detect")
        translate = get_node("translate")
        if lang_detect is None or translate is None:
            raise PlanningError(
                f"Node '{target_node.node_id}' requires English but "
                "lang_detect or translate nodes are not registered"
            )
        steps.append(lang_detect)
        steps.append(translate)

    steps.append(target_node)
    return ExecutionBranch(output_type=output_type, steps=steps)
