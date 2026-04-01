"""Schema validation for templates and flow definitions."""

VALID_TASK_TYPES = {
    "HTTP", "SWITCH", "FORK_JOIN", "DO_WHILE", "SET_VARIABLE",
    "TRANSFORM", "SUB_WORKFLOW", "TERMINATE", "WAIT", "LOG",
}


class TemplateValidationError(Exception):
    pass


def validate_task_template(template: dict):
    """Validate a single task template."""
    if not isinstance(template, dict):
        raise TemplateValidationError("Template must be a dict")

    task_ref = template.get("task_ref")
    if not task_ref:
        raise TemplateValidationError("Template missing required field: task_ref")

    task_type = template.get("type")
    if not task_type:
        raise TemplateValidationError(f"Template '{task_ref}' missing required field: type")

    if task_type not in VALID_TASK_TYPES:
        raise TemplateValidationError(
            f"Template '{task_ref}' has invalid type: '{task_type}'. "
            f"Valid types: {sorted(VALID_TASK_TYPES)}"
        )

    # Type-specific validation
    if task_type == "HTTP":
        _validate_http_task(template)
    elif task_type == "SWITCH":
        _validate_switch_task(template)
    elif task_type == "FORK_JOIN":
        _validate_fork_join_task(template)
    elif task_type == "DO_WHILE":
        _validate_do_while_task(template)
    elif task_type == "SUB_WORKFLOW":
        _validate_sub_workflow_task(template)


def validate_flow_definition(flow: dict):
    """Validate a complete flow definition."""
    if not isinstance(flow, dict):
        raise TemplateValidationError("Flow definition must be a dict")

    flow_id = flow.get("flow_id")
    if not flow_id:
        raise TemplateValidationError("Flow definition missing required field: flow_id")

    tasks = flow.get("tasks")
    if not isinstance(tasks, list):
        raise TemplateValidationError(f"Flow '{flow_id}' missing or invalid 'tasks' list")

    # Check for duplicate task_refs
    task_refs = set()
    _collect_task_refs(tasks, task_refs, flow_id)


def _collect_task_refs(tasks: list, seen: set, flow_id: str):
    """Recursively collect and check for duplicate task_refs."""
    for task in tasks:
        ref = task.get("task_ref")
        if ref:
            if ref in seen:
                raise TemplateValidationError(
                    f"Flow '{flow_id}' has duplicate task_ref: '{ref}'"
                )
            seen.add(ref)

        # Check nested tasks in SWITCH, FORK_JOIN, DO_WHILE
        for case_tasks in task.get("decision_cases", {}).values():
            _collect_task_refs(case_tasks, seen, flow_id)
        if task.get("default_case"):
            _collect_task_refs(task["default_case"], seen, flow_id)
        for branch in task.get("fork_tasks", []):
            _collect_task_refs(branch, seen, flow_id)
        if task.get("loop_over"):
            _collect_task_refs(task["loop_over"], seen, flow_id)


def _validate_http_task(task: dict):
    params = task.get("input_parameters", {})
    http_req = params.get("http_request", params)
    if not http_req.get("url") and not http_req.get("method"):
        pass  # URL might come from interpolation


def _validate_switch_task(task: dict):
    if not task.get("expression"):
        raise TemplateValidationError(
            f"SWITCH task '{task.get('task_ref')}' missing required field: expression"
        )


def _validate_fork_join_task(task: dict):
    if not task.get("fork_tasks"):
        raise TemplateValidationError(
            f"FORK_JOIN task '{task.get('task_ref')}' missing required field: fork_tasks"
        )


def _validate_do_while_task(task: dict):
    if not task.get("loop_condition"):
        raise TemplateValidationError(
            f"DO_WHILE task '{task.get('task_ref')}' missing required field: loop_condition"
        )
    if not task.get("loop_over"):
        raise TemplateValidationError(
            f"DO_WHILE task '{task.get('task_ref')}' missing required field: loop_over"
        )


def _validate_sub_workflow_task(task: dict):
    if not task.get("sub_workflow", {}).get("name"):
        raise TemplateValidationError(
            f"SUB_WORKFLOW task '{task.get('task_ref')}' missing sub_workflow.name"
        )
