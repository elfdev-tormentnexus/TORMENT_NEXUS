#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${TORMENT_NEXUS_PYTHON:-python3}"

cd "$PROJECT_DIR/assistant"
exec "$PYTHON_BIN" "$PROJECT_DIR/assistant/run_regressions.py"
