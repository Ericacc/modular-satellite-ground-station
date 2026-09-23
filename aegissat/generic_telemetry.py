"""Normalise decoded telemetry without knowing satellite field names in advance."""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def _safe_name(value):
    text = str(value).strip() or "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if hasattr(value, "item"):
        return _json_value(value.item())
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def flatten_parameters(data, prefix=""):
    parameters = []

    if isinstance(data, dict):
        for name, value in data.items():
            path = f"{prefix}.{name}" if prefix else str(name)
            parameters.extend(flatten_parameters(value, path))
        return parameters

    if isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            path = f"{prefix}[{index}]"
            parameters.extend(flatten_parameters(value, path))
        return parameters

    name = prefix.rsplit(".", 1)[-1] if prefix else "value"
    name = name.split("[", 1)[0]
    value = _json_value(data)
    parameters.append({
        "name": name,
        "path": prefix or name,
        "value": value,
        "value_type": type(value).__name__,
        "unit": None,
        "metadata_known": False,
    })
    return parameters


def build_generic_telemetry(satellite_id, decoded_data, source,
                            decoder="external", raw_payload=None,
                            reception_timestamp_ms=None):
    if not isinstance(decoded_data, (dict, list, tuple)):
        raise TypeError("Decoded telemetry must be a dictionary or list")

    timestamp_ms = reception_timestamp_ms or int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    document = {
        "schema_version": 1,
        "satellite": {"id": satellite_id or "unknown"},
        "reception": {
            "timestamp": datetime.fromtimestamp(
                timestamp_ms / 1000, timezone.utc
            ).isoformat(),
            "timestamp_ms": timestamp_ms,
            "source": source,
            "decoder": decoder,
        },
        "parameters": flatten_parameters(decoded_data),
        "raw_payload_hex": None,
    }
    if raw_payload is not None:
        document["raw_payload_hex"] = bytes(raw_payload).hex()
    return document


def archive_generic_telemetry(document, directory):
    target_directory = Path(directory)
    target_directory.mkdir(parents=True, exist_ok=True)
    satellite = _safe_name(document["satellite"]["id"])
    timestamp = document["reception"]["timestamp_ms"]
    target = target_directory / f"{satellite}_{timestamp}.json"
    counter = 1
    while target.exists():
        target = target_directory / f"{satellite}_{timestamp}_{counter}.json"
        counter += 1
    target.write_text(
        json.dumps(document, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
