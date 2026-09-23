#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_RECORDINGS_DIR="${RECORDINGS_DIR:-$ROOT/data/recordings}"
INPUT="${1:-ao73.wav}"
PROFILE="${2:-}"
SATELLITE_ID="${3:-}"
API_URL="${AEGISSAT_API_URL:-http://127.0.0.1:8000}"
CONDA_ENV="${GR_SATELLITES_CONDA_ENV:-gr-satellites}"
STARTED_API=0
API_PID=""

finish() {
  if [ "$STARTED_API" -eq 1 ] && [ -n "$API_PID" ]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap finish EXIT INT TERM

if [ -f "$INPUT" ]; then
  WAVFILE="$INPUT"
elif [ -f "$DEFAULT_RECORDINGS_DIR/$INPUT" ]; then
  WAVFILE="$DEFAULT_RECORDINGS_DIR/$INPUT"
else
  echo "[FAIL] Recording not found: $INPUT"
  echo "       Full paths and filenames inside $DEFAULT_RECORDINGS_DIR are accepted."
  exit 2
fi

STEM="$(basename "$WAVFILE")"
STEM="${STEM%.*}"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[FAIL] Project .venv not found. Create it and install the project first."
  exit 2
fi

if [ -z "$PROFILE" ] || [ -z "$SATELLITE_ID" ]; then
  VALUES="$($ROOT/.venv/bin/python - "$ROOT/config/recording_tests.json" "$STEM" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    profile = json.load(file).get(sys.argv[2].lower(), {})
print(profile.get("gr_satellites_name", ""))
print(profile.get("satellite_id", ""))
PY
)"
  INFERRED_PROFILE="$(printf '%s\n' "$VALUES" | sed -n '1p')"
  INFERRED_ID="$(printf '%s\n' "$VALUES" | sed -n '2p')"
  PROFILE="${PROFILE:-$INFERRED_PROFILE}"
  SATELLITE_ID="${SATELLITE_ID:-$INFERRED_ID}"
fi

if [ -z "$PROFILE" ] || [ -z "$SATELLITE_ID" ]; then
  echo "[FAIL] Unknown recording '$STEM'."
  echo "Usage: ./run_recording_test.sh WAVFILE GR_SATELLITES_NAME SATELLITE_ID"
  echo "Example: ./run_recording_test.sh recording.wav 'FUNcube-1' ao-73"
  exit 2
fi


echo "=========================================================="
echo " GR-SATELLITES RECORDING - END-TO-END TEST"
echo "=========================================================="
echo "Recording:    $WAVFILE"
echo "Decoder:      $PROFILE"
echo "Satellite ID: $SATELLITE_ID"

mkdir -p "$ROOT/test_reports"

if ! "$ROOT/.venv/bin/python" - "$API_URL/health" <<'PY' >/dev/null 2>&1
import sys
import urllib.request
urllib.request.urlopen(sys.argv[1], timeout=2).read()
PY
then
  echo "[INFO] Starting API temporarily"
  (
    cd "$ROOT"
    "$ROOT/.venv/bin/python" -m uvicorn aegissat.api:app \
      --host 127.0.0.1 --port 8000 >test_reports/recording_api.log 2>&1
  ) &
  API_PID=$!
  STARTED_API=1
  READY=0
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if "$ROOT/.venv/bin/python" - "$API_URL/health" <<'PY' >/dev/null 2>&1
import sys
import urllib.request
urllib.request.urlopen(sys.argv[1], timeout=2).read()
PY
    then
      READY=1
      break
    fi
    sleep 1
  done
  if [ "$READY" -ne 1 ]; then
    echo "[FAIL] API did not become ready. See test_reports/recording_api.log"
    exit 3
  fi
fi

OUTPUT="$ROOT/test_reports/${STEM}_decoder_output.txt"
KISS="$ROOT/test_reports/${STEM}_frames.kiss"
PASS_ID="recording-${STEM}-$(date +%Y%m%d-%H%M%S)"

if command -v conda >/dev/null 2>&1 && \
  conda env list 2>/dev/null | awk '{print $1}' | grep -qx "$CONDA_ENV"; then

  echo "[INFO] Using Conda environment: $CONDA_ENV"
  CONDA_BASE="$(conda info --base)"

  DECODER_OK=0
  (
    source "$CONDA_BASE/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV"
    export DYLD_LIBRARY_PATH="$CONDA_PREFIX/lib"
    export DYLD_FALLBACK_LIBRARY_PATH="$CONDA_PREFIX/lib"

    python -c "from gnuradio import gr" &&
    python "$ROOT/scripts/gr_satellites_to_station.py" \
      "$PROFILE" \
      --wavfile "$WAVFILE" \
      --satellite-id "$SATELLITE_ID" \
      --pass-id "$PASS_ID" \
      --api-url "$API_URL" \
      --kiss-out "$KISS" \
      --output-file "$OUTPUT"
  ) && DECODER_OK=1

else
  echo "[INFO] Using system GNU Radio and gr-satellites"

  DECODER_OK=0
  /usr/bin/python3 -c "from gnuradio import gr" &&
  /usr/bin/python3 "$ROOT/scripts/gr_satellites_to_station.py" \
    "$PROFILE" \
    --wavfile "$WAVFILE" \
    --satellite-id "$SATELLITE_ID" \
    --pass-id "$PASS_ID" \
    --api-url "$API_URL" \
    --kiss-out "$KISS" \
    --output-file "$OUTPUT" &&
  DECODER_OK=1
fi

if [ "$DECODER_OK" -ne 1 ]; then
  echo "[FAIL] gr-satellites decoding or API ingestion failed"
  exit 4
fi

COUNT="$($ROOT/.venv/bin/python - "$API_URL/openmct/dictionary" "$SATELLITE_ID" <<'PY'
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=10) as response:
    dictionary = json.load(response)
prefix = f"external.{sys.argv[2]}."
print(sum(item["key"].startswith(prefix) for item in dictionary["measurements"]))
PY
)"

if [ "$COUNT" -le 0 ]; then
  echo "[FAIL] No $SATELLITE_ID parameters were discovered by Open MCT"
  exit 5
fi

echo "[PASS] WAV decoded, telemetry ingested and $COUNT Open MCT parameters discovered"
echo "KISS:   $KISS"
echo "Output: $OUTPUT"
