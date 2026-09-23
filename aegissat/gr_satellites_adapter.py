"""Convert gr-satellites' Construct output into generic telemetry dictionaries."""

import ast


def _scalar(text):
    text = text.strip()
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def parse_construct_container(text):
    """Parse the indented Container/ListContainer representation from Construct."""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    root_index = next(
        (index for index, line in enumerate(lines)
         if line.strip() == "Container:"),
        None,
    )
    if root_index is None:
        raise ValueError("No Container found in gr-satellites output")

    root = {}
    stack = [(root, -1)]
    for line in lines[root_index + 1:]:
        content = line.strip()
        if content.startswith("-"):
            break
        indent = len(line) - len(line.lstrip())
        while len(stack) > 1 and indent <= stack[-1][1]:
            stack.pop()
        parent = stack[-1][0]

        if " = " in content:
            name, value_text = content.split(" = ", 1)
            if value_text == "Container:":
                value = {}
                parent[name] = value
                stack.append((value, indent))
            elif value_text == "ListContainer:":
                value = []
                parent[name] = value
                stack.append((value, indent))
            else:
                parent[name] = _scalar(value_text)
            continue

        if content == "Container:" and isinstance(parent, list):
            value = {}
            parent.append(value)
            stack.append((value, indent))
        elif content == "ListContainer:" and isinstance(parent, list):
            value = []
            parent.append(value)
            stack.append((value, indent))
        elif isinstance(parent, list):
            parent.append(_scalar(content))

    return root


def extract_realtime_telemetry(output):
    """Return every realtime telemetry Container printed by gr-satellites."""
    documents = []
    marker = "Realtime telemetry:"
    position = 0
    while True:
        start = output.find(marker, position)
        if start < 0:
            break
        container_start = output.find("Container:", start + len(marker))
        if container_start < 0:
            break
        next_marker = output.find(marker, container_start + len("Container:"))
        segment_end = next_marker if next_marker >= 0 else len(output)
        segment = output[container_start:segment_end]
        documents.append(parse_construct_container(segment))
        position = segment_end
    return documents
