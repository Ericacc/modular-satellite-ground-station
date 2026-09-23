import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from aegissat.config import PROJECT_ROOT, env_float, env_int


SATNOGS_TRANSMITTERS_URL = "https://db.satnogs.org/api/transmitters/"


def _download_json(url):
    request = Request(url, headers={"User-Agent": "AegisSat-Ground-Station/1.0"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def update_transmitter_cache(cache_path=None, max_age_hours=None):
    path = Path(cache_path or os.getenv(
        "SATNOGS_CACHE_PATH", PROJECT_ROOT / "data" / "transmitters.json"
    ))
    age = max_age_hours
    if age is None:
        age = env_float("CATALOG_REFRESH_HOURS", 12)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = path.exists() and time.time() - path.stat().st_mtime < age * 3600
    if fresh:
        return path
    try:
        url = os.getenv("SATNOGS_TRANSMITTERS_URL", SATNOGS_TRANSMITTERS_URL)
        data = _download_json(url + "?" + urlencode({"format": "json"}))
        if isinstance(data, dict):
            data = data.get("results", [])
        if not isinstance(data, list):
            raise ValueError("SatNOGS DB returned an invalid transmitter catalogue")
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        if not path.exists():
            raise
    return path


def discover_satellites(cache_path=None):
    transmitters = json.loads(update_transmitter_cache(cache_path).read_text(encoding="utf-8"))
    minimum_hz = env_int("AUTO_MIN_FREQUENCY_HZ", 137_000_000)
    maximum_hz = env_int("AUTO_MAX_FREQUENCY_HZ", 470_000_000)
    maximum_satellites = env_int("AUTO_MAX_SATELLITES", 40)
    by_norad = {}
    for transmitter in transmitters:
        status = str(transmitter.get("status", "")).lower()
        if status not in {"active", "alive"}:
            continue
        norad = transmitter.get("norad_cat_id") or transmitter.get("norad_cat_id_old")
        frequency = transmitter.get("downlink_low") or transmitter.get("downlink_high")
        if not norad or not frequency:
            continue
        frequency = int(float(frequency))
        if not minimum_hz <= frequency <= maximum_hz:
            continue
        norad = int(norad)
        candidate = {
            "id": f"norad-{norad}",
            "name": transmitter.get("description") or f"NORAD {norad}",
            "norad_id": norad,
            "downlink_frequency_hz": frequency,
            "mode": transmitter.get("mode") or "unknown",
            "baud_rate": transmitter.get("baud"),
            "decoder": "iq_recording",
            "transmitter_uuid": transmitter.get("uuid"),
            "source": "satnogs-db",
        }
        by_norad.setdefault(norad, candidate)
        if len(by_norad) >= maximum_satellites:
            break
    return list(by_norad.values())
