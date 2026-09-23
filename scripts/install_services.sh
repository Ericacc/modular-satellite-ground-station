#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    echo "Run this script as the target user, without sudo."
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
GROUP_NAME="$(id -gn)"
USER_HOME="$HOME"

install_service() {
    local source="$1"
    local target="$2"

    sed \
        -e "s|__USER__|$USER_NAME|g" \
        -e "s|__GROUP__|$GROUP_NAME|g" \
        -e "s|__HOME__|$USER_HOME|g" \
        -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
        "$source" | sudo tee "$target" >/dev/null
}

install_service \
    "$PROJECT_DIR/deployment/systemd/aegissat-api.service" \
    "/etc/systemd/system/aegissat-api.service"

install_service \
    "$PROJECT_DIR/deployment/systemd/aegissat-openmct.service" \
    "/etc/systemd/system/aegissat-openmct.service"

sudo systemctl daemon-reload
sudo systemctl enable aegissat-api.service
sudo systemctl enable aegissat-openmct.service

echo "Systemd services installed."
echo "Start the ground station with: ./start_ground_station.sh"
