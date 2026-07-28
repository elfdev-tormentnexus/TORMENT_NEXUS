#!/bin/sh
set -eu

# This script lives in setup/, so the project root is one level up.
cd "$(dirname "$0")/.."
python3 assistant/hardware/setup_hardware.py

