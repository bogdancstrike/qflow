"""Flask-RESTX request/response model schemas."""

from flask_restx import fields


def register_models(api):
    """Register API models with Flask-RESTX for Swagger documentation."""

    task_input_model = api.model("TaskInput", {
        "input_type": fields.String(
            required=True,
            description="Input type: file_upload, text, or youtube_link",
            enum=["file_upload", "text", "youtube_link"],
        ),
        "input_data": fields.Raw(
            required=True,
            description="Input data: text content, YouTube URL, or file metadata",
        ),
        "desired_output": fields.String(
            required=True,
            description="Desired output type: stt, ner, sentiment, summary, etc.",
        ),
    })

    task_response_model = api.model("TaskResponse", {
        "id": fields.String(description="Task ID"),
        "input_type": fields.String(),
        "input_data": fields.Raw(),
        "desired_output": fields.String(),
        "resolved_flow": fields.String(),
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
