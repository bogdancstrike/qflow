"""SUB_WORKFLOW operator — invokes another flow definition as a child."""

from framework.commons.logger import logger

from src.core.operators.base import BaseOperator
from src.core.interpolator import interpolate
from src.config import Config


class SubWorkflowOperator(BaseOperator):
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        task_ref = task_def.get("task_ref", "unknown")
        sub_workflow = task_def.get("sub_workflow", {})
        input_params = task_def.get("input_parameters", {})

        flow_name = sub_workflow.get("name")
        if not flow_name:
            raise ValueError(f"SUB_WORKFLOW {task_ref}: missing sub_workflow.name")

        # Check nesting depth
        if context.depth >= Config.MAX_SUB_WORKFLOW_DEPTH:
            raise RuntimeError(
                f"SUB_WORKFLOW {task_ref}: max nesting depth ({Config.MAX_SUB_WORKFLOW_DEPTH}) exceeded"
            )

        # Resolve input parameters
        resolved_inputs = interpolate(input_params, context)

        logger.info(f"[SUB_WORKFLOW] {task_ref}: invoking flow '{flow_name}' at depth {context.depth + 1}")

        # Load and execute sub-flow
        from src.templating.registry import get_flow
        from src.core.executor import execute_flow

        flow_def = get_flow(flow_name)
        if flow_def is None:
            raise ValueError(f"SUB_WORKFLOW {task_ref}: flow '{flow_name}' not found")

        # Create child context
        child_ctx = context.child_context(resolved_inputs)

        result = execute_flow(flow_def, child_ctx, task_id)

        logger.info(f"[SUB_WORKFLOW] {task_ref}: flow '{flow_name}' completed")
        return result
