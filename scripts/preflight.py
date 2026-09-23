#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

from aegissat.catalog import discover_satellites, update_transmitter_cache
from aegissat.orbit import load_tle_by_norad


def check_command(name, arguments=None):
    path = shutil.which(name)
    if not path:
        return False, "not found"
    if arguments:
        try:
            result = subprocess.run([path, *arguments], capture_output=True, text=True, timeout=15)
            return result.returncode == 0, (result.stdout + result.stderr).strip()[-300:]
        except subprocess.TimeoutExpired:
            return False, "command timed out after 15 seconds"
    return True, path


def main():
    results = {}
    results["python"] = {"ok": sys.version_info >= (3, 10), "detail": sys.version.split()[0]}
    ok, detail = check_command("rtl_test", ["-t"])
    results["rtl_test"] = {"ok": ok, "detail": detail}
    gr_ok, gr_detail = check_command("gr_satellites", ["--list_satellites"])
    results["gr_satellites_optional"] = {"ok": True, "detail": gr_detail if gr_ok else "not installed; IQ recording remains available"}
    try:
        path = update_transmitter_cache(max_age_hours=0)
        profiles = discover_satellites(path)
        results["satnogs_catalog"] = {"ok": bool(profiles), "detail": f"{len(profiles)} compatible satellites"}
        name, _, _ = load_tle_by_norad(profiles[0]["norad_id"])
        results["celestrak"] = {"ok": True, "detail": name}
    except Exception as error:
        results["automatic_catalog"] = {"ok": False, "detail": str(error)}
    if os.getenv("STORAGE_BACKEND", "memory") == "influxdb":
        try:
            with urlopen(os.getenv("INFLUX_URL", "http://127.0.0.1:8086") + "/health", timeout=5) as response:
                results["influxdb"] = {"ok": response.status == 200, "detail": response.status}
        except Exception as error:
            results["influxdb"] = {"ok": False, "detail": str(error)}
    else:
        results["influxdb"] = {"ok": True, "detail": "memory backend selected"}
    print(json.dumps(results, indent=2))
    return 0 if all(item["ok"] for item in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
