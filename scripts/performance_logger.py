#!/usr/bin/env python3

import argparse
import csv
import json
import subprocess
import time

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def get_receiver_status(api_url):
    try:
        with urlopen(f"{api_url}/receiver/status", timeout=1) as response:
            return json.load(response)
    except Exception:
        return {}


def find_process(name):
    if not name:
        return None

    try:
        result = subprocess.run(
            ["pgrep", "-n", "-f", name],
            capture_output=True,
            text=True
        )

        value = result.stdout.strip()

        if value:
            return int(value)

    except Exception:
        pass

    return None


def get_process_stats(pid):
    if not pid:
        return "", ""

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "%cpu=,rss="],
            capture_output=True,
            text=True
        )

        values = result.stdout.strip().split()

        if len(values) < 2:
            return "", ""

        cpu = values[0]
        ram_mb = round(int(values[1]) / 1024, 2)

        return cpu, ram_mb

    except Exception:
        return "", ""


def get_cpu_temperature():
    path = Path("/sys/class/thermal/thermal_zone0/temp")

    try:
        return round(int(path.read_text().strip()) / 1000, 1)
    except Exception:
        return ""


def get_system_ram():
    try:
        values = {}

        with open("/proc/meminfo") as file:
            for line in file:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0])

        used = values["MemTotal"] - values["MemAvailable"]

        return round(used / 1024, 2)

    except Exception:
        return ""


def get_iq_size(iq_dir, pass_id):
    if not pass_id:
        return ""

    path = Path(iq_dir) / f"{pass_id}.c64"

    if not path.exists():
        return ""

    return round(
        path.stat().st_size / (1024 * 1024),
        2
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--output", required=True)

    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000"
    )

    parser.add_argument(
        "--iq-dir",
        default="data/iq"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1
    )

    parser.add_argument(
        "--process-name",
        default=""
    )

    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "timestamp_utc",
        "receiver_running",
        "process_pid",
        "process_cpu_percent",
        "process_ram_mb",
        "pass_id",
        "system_ram_used_mb",
        "cpu_temperature_c",
        "iq_file_mb"
    ]

    with output.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        file.flush()

        while True:
            status = get_receiver_status(
                args.api_url
            )

            pid = status.get("pid")

            if args.process_name:
                process_pid = find_process(
                    args.process_name
                )

                if process_pid:
                    pid = process_pid

            pass_id = status.get("pass_id")

            cpu, ram = get_process_stats(pid)

            writer.writerow({
                "timestamp_utc":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                "receiver_running":
                    status.get(
                        "running",
                        False
                    ),

                "process_pid":
                    pid or "",

                "process_cpu_percent":
                    cpu,

                "process_ram_mb":
                    ram,

                "pass_id":
                    pass_id or "",

                "system_ram_used_mb":
                    get_system_ram(),

                "cpu_temperature_c":
                    get_cpu_temperature(),

                "iq_file_mb":
                    get_iq_size(
                        args.iq_dir,
                        pass_id
                    )
            })

            file.flush()

            time.sleep(args.interval)


if __name__ == "__main__":
    main()
