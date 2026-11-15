#!/bin/sh
# Runs the CI workflow's steps locally and writes a transcript to evidence/ci-local-<date>.txt.
# Usage: sh tools/ci_local.sh            (from anywhere inside the repository)
set -u
cd "$(dirname "$0")/.."
out="evidence/ci-local-$(date -u +%Y-%m-%d).txt"
log=$(mktemp)
trap 'rm -f "$log"' EXIT
mkdir -p evidence
fail=0
cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2)
[ -n "$cpu" ] || cpu=unknown
{
  echo "# CI steps run locally, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo "cpu: $cpu"
  for step in "fe fmt --check" "fe check" "fe build" "fe test" "fe test --backend native"; do
    echo
    echo "## $step"
    $step > "$log" 2>&1
    status=$?
    grep -v '^Wrote ' "$log"
    if [ "$status" -eq 0 ]; then echo "-> PASS"; else echo "-> FAIL (exit $status)"; fail=1; fi
  done
  echo
  if [ "$fail" -eq 0 ]; then echo "RESULT: all steps passed"; else echo "RESULT: at least one step failed"; fi
} > "$out" 2>&1
cat "$out"
exit "$fail"
