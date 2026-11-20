#!/bin/sh
# Deterministic benchmarks: sh bench/run.sh [--skip-budget] [--date YYYY-MM-DD]  ->  evidence/bench-<date>.{json,md}
set -eu
cd "$(dirname "$0")/.."
exec python3 bench/run.py "$@"
