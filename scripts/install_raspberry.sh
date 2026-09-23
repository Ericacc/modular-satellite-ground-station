#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "Warning: this installer is intended for 64-bit Raspberry Pi OS (aarch64)."
fi

sudo apt-get update
sudo apt-get install -y python3-venv python3-dev rtl-sdr libusb-1.0-0 nodejs npm

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e '.[test]'
npm --prefix openmct install

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Set station coordinates and InfluxDB values before service installation."
fi

.venv/bin/pytest -q
echo "Software installation complete."
echo "Preflight: .venv/bin/python scripts/preflight.py"
echo "Open MCT: npm --prefix openmct start"
