#!/usr/bin/env python3
"""Decode a recording with gr-satellites and send its telemetry to the API."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aegissat.gr_satellites_adapter import extract_realtime_telemetry


def post_document(api_url, satellite_id, pass_id, parameters):
    payload = {
        "satellite_id": satellite_id,
        "source": "gr_satellites_wav",
        "decoder": "gr-satellites",
        "pass_id": pass_id,
        "parameters": parameters,
    }
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/ingest/decoded-telemetry",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="gr-satellites WAV to AegisSat generic telemetry adapter"
    )
    parser.add_argument("satellite", help="gr-satellites name, e.g. FUNcube-1")
    parser.add_argument("--wavfile", required=True)
    parser.add_argument("--satellite-id", required=True)
    parser.add_argument("--pass-id", default="gr-satellites-recording")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--kiss-out")
    parser.add_argument(
        "--output-file",
        help="Optional file in which to preserve the decoder's complete output",
    )
    args = parser.parse_args()

    command = ["gr_satellites", args.satellite, "--wavfile", args.wavfile]
    if args.kiss_out:
        command.extend(["--kiss_out", args.kiss_out])

    print("Running:", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    print(result.stdout, end="")
    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as output_file:
            output_file.write(result.stdout)
    if result.returncode != 0:
        print(f"gr-satellites failed with exit code {result.returncode}", file=sys.stderr)
        return result.returncode

    documents = extract_realtime_telemetry(result.stdout)
    if not documents:
        print("No realtime telemetry Container was recovered", file=sys.stderr)
        return 2

    try:
        for index, parameters in enumerate(documents, start=1):
            status, response = post_document(
                args.api_url,
                args.satellite_id,
                args.pass_id,
                parameters,
            )
            count = len(response["generic_telemetry"]["parameters"])
            print(f"Uploaded telemetry {index}: HTTP {status}, {count} parameters")
    except urllib.error.HTTPError as error:
        print(f"API HTTP {error.code}: {error.read().decode('utf-8')}", file=sys.stderr)
        return 3
    except urllib.error.URLError as error:
        print(f"API connection failed: {error.reason}", file=sys.stderr)
        return 3

    print(f"Completed: {len(documents)} telemetry document(s) uploaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
