"""Abstract base operator interface.

Every operator implements execute(task_def, context, task_id) -> output.
"""

from abc import ABC, abstractmethod


class BaseOperator(ABC):
    @abstractmethod
    def execute(self, task_def: dict, context, task_id: str = None) -> dict:
        """Execute the task and return its output.

        Args:
            task_def: The task definition from the flow JSON.
            context: ExecutionContext with workflow input, step outputs, variables.
            task_id: The parent task ID (for logging).

        Returns:
            The task output (dict or any serializable value).

        Raises:
            TerminateFlowException: If the flow should stop early (TERMINATE operator).
            Exception: On unrecoverable errors.
        """
        pass


class TerminateFlowException(Exception):
    """Raised by TERMINATE operator to halt flow execution."""

    def __init__(self, status: str, reason: str, output: dict = None):
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.output = output or {}
