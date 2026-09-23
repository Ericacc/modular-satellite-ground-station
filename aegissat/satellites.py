import json
from pathlib import Path

from aegissat.catalog import discover_satellites


DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "satellites.json"


def load_satellites(path=DEFAULT_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    satellites = data.get("satellites", [])
    required = {"id", "norad_id", "downlink_frequency_hz", "decoder"}
    for satellite in satellites:
        missing = required - satellite.keys()
        if missing:
            raise ValueError(f"Satellite profile is missing: {sorted(missing)}")
        satellite.setdefault("enabled", True)
    return satellites


def load_all_satellites(path=DEFAULT_PATH):
    local = load_satellites(path)
    automatic = discover_satellites()

    overrides = {
        item["norad_id"]: item
        for item in local
        if item.get("norad_id")
    }

    result = []
    discovered_norad_ids = set()

    for item in automatic:
        norad_id = item["norad_id"]
        discovered_norad_ids.add(norad_id)

        if norad_id in overrides:
            item.update(overrides[norad_id])

        result.append(item)

    result.extend(
        item
        for item in local
        if (
            not item.get("norad_id")
            or item["norad_id"] not in discovered_norad_ids
        )
    )

    return result


def get_satellite(satellite_id, path=DEFAULT_PATH):
    for satellite in load_all_satellites(path):
        if satellite["id"] == satellite_id:
            return satellite
    raise KeyError(f"Unknown satellite profile: {satellite_id}")
