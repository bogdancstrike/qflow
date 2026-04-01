"""Input validation for API requests."""

from src.core.resolver import is_valid_combination, get_valid_outputs, get_valid_input_types_for_output

VALID_INPUT_TYPES = {"file_upload", "text", "youtube_link"}


def validate_task_input(data: dict) -> list:
    """Validate task creation input. Returns list of error messages (empty if valid)."""
    errors = []

    input_type = data.get("input_type")
    if not input_type:
        errors.append("'input_type' is required")
    elif input_type not in VALID_INPUT_TYPES:
        errors.append(f"Invalid input_type '{input_type}'. Valid: {sorted(VALID_INPUT_TYPES)}")

    desired_output = data.get("desired_output")
    if not desired_output:
        errors.append("'desired_output' is required")
    elif desired_output not in get_valid_outputs():
        errors.append(
            f"Invalid desired_output '{desired_output}'. "
            f"Valid: {get_valid_outputs()}"
        )

    if input_type and desired_output and not errors:
        if not is_valid_combination(input_type, desired_output):
            valid_inputs = get_valid_input_types_for_output(desired_output)
            errors.append(
                f"Input type '{input_type}' is not supported for desired_output "
                f"'{desired_output}'. Valid input types: {valid_inputs}"
            )

    # Validate input_data based on input_type
    if not errors:
        input_data = data.get("input_data")
        if input_type == "text":
            if not input_data or not isinstance(input_data, (str, dict)):
                errors.append("'input_data' must be a non-empty string or JSON object for text input")
        elif input_type == "youtube_link":
            if not input_data or not isinstance(input_data, str):
                errors.append("'input_data' must be a YouTube URL string")
        elif input_type == "file_upload":
            # File uploads are handled separately via multipart form
            pass

    return errors
