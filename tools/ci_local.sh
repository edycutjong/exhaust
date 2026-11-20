#!/bin/sh
# Runs the CI workflow's steps locally and prints a transcript; with EVIDENCE=1 it is saved to
# evidence/ci-local-<date>.txt (only when every step passed).
# Usage: sh tools/ci_local.sh            (from anywhere inside the repository)
set -u
cd "$(dirname "$0")/.."
keep="evidence/ci-local-$(date -u +%Y-%m-%d).txt"
out=$(mktemp)
log=$(mktemp)
trap 'rm -f "$log" "$out"' EXIT
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
  for step in "fe fmt --check" "fe check" "fe build" "fe test" "fe test --backend native" "sh demo/run.sh" "sh demo/check-bugs.sh" "sh demo/check-bugs.sh --conformance" "python3 -I tools/ref_model.py --check"; do
    echo
    echo "## $step"
    t0=$(python3 -c 'import time; print(time.time())')
    $step > "$log" 2>&1
    status=$?
    t1=$(python3 -c 'import time; print(time.time())')
    grep -v '^Wrote ' "$log"
    secs=$(python3 -c "print(f'{$t1 - $t0:.2f}')")
    if [ "$status" -eq 0 ]; then echo "-> PASS (${secs} s wall)"; else echo "-> FAIL (exit $status, ${secs} s wall)"; fail=1; fi
  done
  echo
  if [ "$fail" -eq 0 ]; then echo "RESULT: all steps passed"; else echo "RESULT: at least one step failed"; fi
} > "$out" 2>&1
cat "$out"
if [ "${EVIDENCE:-0}" = 1 ] && [ "$fail" -eq 0 ]; then cp "$out" "$keep"; fi
exit "$fail"
