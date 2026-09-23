#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="${PYTHON:-python3}"
fi

exec "$PYTHON" "$PROJECT_DIR/scripts/run_all_tests.py" "$@"
