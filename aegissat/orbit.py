import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from aegissat.config import PROJECT_ROOT, env_float, env_int


def update_tle_cache(norad_id=None, url=None, cache_path=None, max_age_hours=None):
    if norad_id is not None:
        url = url or (
            "https://celestrak.org/NORAD/elements/gp.php?"
            f"CATNR={int(norad_id)}&FORMAT=tle"
        )
    else:
        url = url or os.getenv(
            "TLE_URL",
            "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=tle",
        )
    default_name = f"tle-{int(norad_id)}.txt" if norad_id is not None else "tle.txt"
    cache_path = Path(cache_path or PROJECT_ROOT / "data" / default_name)
    if max_age_hours is None:
        max_age_hours = env_float("TLE_REFRESH_HOURS", 12)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    fresh = cache_path.exists() and time.time() - cache_path.stat().st_mtime < max_age_hours * 3600
    if fresh:
        return cache_path
    try:
        request = Request(url, headers={"User-Agent": "AegisSat-Ground-Station/1.0"})
        with urlopen(request, timeout=15) as response:
            content = response.read()
        if not content.strip() or b"<html" in content[:500].lower():
            raise ValueError("TLE source returned an empty response")
        lines = [line.strip() for line in content.decode("utf-8").splitlines() if line.strip()]
        if len(lines) < 3 or not any(line.startswith("1 ") for line in lines):
            raise ValueError("TLE source did not return valid 3LE data")
        cache_path.write_bytes(content)
    except Exception:
        if not cache_path.exists():
            raise
    return cache_path


def load_tle_by_norad(norad_id, cache_path=None):
    path = update_tle_cache(norad_id=norad_id, cache_path=cache_path)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    target = str(int(norad_id))
    for index in range(len(lines) - 2):
        catalog = lines[index + 1][2:7].lstrip("0") or "0"
        if lines[index + 1].startswith("1 ") and catalog == target:
            return lines[index], lines[index + 1], lines[index + 2]
    raise KeyError(f"NORAD {norad_id} was not found in the TLE cache")


def calculate_passes(norad_id, hours=24, minimum_elevation_deg=None, cache_path=None):
    from skyfield.api import EarthSatellite, load, wgs84

    minimum = minimum_elevation_deg
    if minimum is None:
        minimum = env_float("MIN_ELEVATION_DEG", 10)
    name, line1, line2 = load_tle_by_norad(norad_id, cache_path)
    timescale = load.timescale()
    satellite = EarthSatellite(line1, line2, name, timescale)
    station = wgs84.latlon(
        env_float("GROUND_STATION_LAT", 0.0),
        env_float("GROUND_STATION_LON", 0.0),
        elevation_m=env_float("GROUND_STATION_ALT_M", 0),
    )
    start = timescale.now()
    end = timescale.tt_jd(start.tt + hours / 24)
    times, events = satellite.find_events(station, start, end, altitude_degrees=minimum)
    passes = []
    current = None
    for event_time, event in zip(times, events):
        instant = event_time.utc_datetime().replace(tzinfo=timezone.utc)
        if event == 0:
            current = {"start": instant.isoformat(), "maximum": None, "end": None}
        elif event == 1 and current:
            altitude, azimuth, _ = (satellite - station).at(event_time).altaz()
            current["maximum"] = instant.isoformat()
            current["maximum_elevation_deg"] = float(altitude.degrees)
            current["maximum_azimuth_deg"] = float(azimuth.degrees)
        elif event == 2 and current:
            current["end"] = instant.isoformat()
            passes.append(current)
            current = None
    return passes
