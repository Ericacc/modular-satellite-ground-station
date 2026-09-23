#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://127.0.0.1:8000/health"
OPENMCT_URL="http://127.0.0.1:8080"
INFLUX_URL="http://127.0.0.1:8086/health"

cd "$ROOT"

echo "========================================"
echo " Modular Satellite Ground Station"
echo "========================================"

echo "[1/4] Starting InfluxDB..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d influxdb
elif docker compose version >/dev/null 2>&1; then
    docker compose up -d influxdb
else
    echo "[ERROR] Docker Compose is not available."
    exit 1
fi

echo "[2/4] Starting the API..."
sudo systemctl start aegissat-api.service

echo "[3/4] Starting Open MCT..."
sudo systemctl start aegissat-openmct.service

echo "[4/4] Waiting for services..."

wait_for_url() {
    local name="$1"
    local url="$2"

    for attempt in $(seq 1 30); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            echo "[OK] $name"
            return 0
        fi

        sleep 1
    done

    echo "[ERROR] $name did not become available."
    return 1
}

wait_for_url "InfluxDB" "$INFLUX_URL"
wait_for_url "API" "$API_URL"
wait_for_url "Open MCT" "$OPENMCT_URL"

echo
echo "Service status:"
systemctl is-active aegissat-api.service
systemctl is-active aegissat-openmct.service
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo
curl -fsS "$API_URL" | python3 -m json.tool

echo
echo "Station ready."
echo "API:      http://127.0.0.1:8000"
echo "Open MCT: http://127.0.0.1:8080"
echo "InfluxDB: http://127.0.0.1:8086"
