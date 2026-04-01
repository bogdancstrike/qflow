"""Execution context — holds inter-step data, workflow variables, and input."""

from copy import deepcopy


class ExecutionContext:
    def __init__(self, workflow_input: dict, env: dict = None):
        self.workflow_input = deepcopy(workflow_input)
        self.env = env or {}
        self.steps = {}  # {task_ref: {"output": {...}, "status": "...", "duration_ms": ...}}
        self.variables = {}  # Set by SET_VARIABLE tasks
        self._depth = 0  # Sub-workflow nesting depth

    def set_step_output(self, task_ref: str, output, status: str = "SUCCESS", duration_ms: int = 0):
        self.steps[task_ref] = {
            "output": output,
            "status": status,
            "duration_ms": duration_ms,
        }

    def get_step_output(self, task_ref: str):
        step = self.steps.get(task_ref)
        if step:
            return step.get("output")
        return None

    def set_variable(self, name: str, value):
        self.variables[name] = value

    def get_variable(self, name: str, default=None):
        return self.variables.get(name, default)

    def child_context(self, workflow_input: dict):
        """Create a child context for sub-workflow execution."""
        child = ExecutionContext(workflow_input, self.env)
        child._depth = self._depth + 1
        return child

    @property
    def depth(self):
        return self._depth

    def to_dict(self):
        return {
            "workflow_input": self.workflow_input,
            "steps": self.steps,
            "variables": self.variables,
        }
