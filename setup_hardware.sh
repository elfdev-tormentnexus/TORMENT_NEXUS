#!/bin/sh
set -eu

cd "$(dirname "$0")"
python3 assistant/hardware/setup_hardware.py

