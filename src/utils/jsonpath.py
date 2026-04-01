"""Lightweight JSONPath-like extraction utility.

Supports dot-notation paths like:
  $.response.body.result.transcription
  $.text
  $.entities[0].name
"""


def extract(data, path: str):
    if not path or path == "$":
        return data

    # Strip leading "$."
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]

    current = data
    for part in _split_path(path):
        if current is None:
            return None
        if isinstance(part, int):
            if isinstance(current, (list, tuple)) and 0 <= part < len(current):
                current = current[part]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def _split_path(path: str):
    parts = []
    for segment in path.split("."):
        # Handle array indexing: entities[0]
        if "[" in segment:
            key, rest = segment.split("[", 1)
            if key:
                parts.append(key)
            idx = rest.rstrip("]")
            try:
                parts.append(int(idx))
            except ValueError:
                parts.append(idx)
        else:
            parts.append(segment)
    return parts
