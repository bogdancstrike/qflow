"""Flask-RESTX request/response model schemas."""

from flask_restx import fields


def register_models(api):
    """Register API models with Flask-RESTX for Swagger documentation."""

    task_input_model = api.model("TaskInput", {
        "input_data": fields.Raw(
            required=True,
            description="Input data: {'text': '...'}, {'file_path': '...'}, or {'url': 'youtube-url'}",
        ),
        "outputs": fields.List(
            fields.String(),
            required=True,
            description="List of desired output types: ner_result, sentiment_result, summary, etc.",
        ),
        "input_type": fields.String(
            description="Optional input type hint (auto-detected if omitted)",
        ),
    })

    task_response_model = api.model("TaskResponse", {
        "id": fields.String(description="Task ID"),
        "input_type": fields.String(),
        "input_data": fields.Raw(),
        "outputs": fields.List(fields.String()),
        "execution_plan": fields.Raw(),
        "status": fields.String(),
        "current_step": fields.String(),
        "step_results": fields.Raw(),
        "workflow_variables": fields.Raw(),
        "final_output": fields.Raw(),
        "error": fields.Raw(),
        "retry_count": fields.Integer(),
        "created_at": fields.String(),
        "updated_at": fields.String(),
    })

    error_model = api.model("Error", {
        "message": fields.String(description="Error message"),
        "errors": fields.List(fields.String(), description="Validation errors"),
    })

    return {
        "task_input": task_input_model,
        "task_response": task_response_model,
        "error": error_model,
    }
