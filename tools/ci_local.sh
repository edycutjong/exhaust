#!/bin/sh
# Runs the CI workflow's steps locally and prints a transcript; with EVIDENCE=1 it is saved to
# evidence/ci-local-<date>.txt (only when every step ran and passed). Exit 0 all passed, 1 a step failed,
# 3 nothing failed but a step was skipped (a missing tool).
# Usage: sh tools/ci_local.sh            (from anywhere inside the repository)
set -u
cd "$(dirname "$0")/.."
keep="evidence/ci-local-$(date -u +%Y-%m-%d).txt"
out=$(mktemp)
log=$(mktemp)
trap 'rm -f "$log" "$out"' EXIT
mkdir -p evidence
fail=0
skipped=""  # a skipped step is never reported as passed, and no evidence is saved from a run that skipped one
cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2)
[ -n "$cpu" ] || cpu=unknown
{
  echo "# CI steps run locally, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo "cpu: $cpu"
  for step in "fe fmt --check" "fe check" "fe build" "fe test" "fe test --backend native" "sh demo/run.sh" "sh demo/check-bugs.sh" "sh demo/check-bugs.sh --conformance" "sh tools/test_gates.sh" "python3 -I tools/ref_model.py --check" "sh bench/run.sh --quick --date ci" "sh tools/transition_coverage.sh" "sh tools/leak_scan.sh" "actionlint .github/workflows/ci.yml .github/workflows/security.yml .github/workflows/release.yml"; do
    echo
    echo "## $step"
    t0=$(python3 -c 'import time; print(time.time())')
    case "$step" in actionlint*) command -v actionlint >/dev/null 2>&1 || { echo "-> SKIPPED (actionlint not installed here)"; skipped="$skipped actionlint"; continue; } ;; esac
    $step > "$log" 2>&1
    status=$?
    t1=$(python3 -c 'import time; print(time.time())')
    grep -v '^Wrote ' "$log"
    secs=$(python3 -c "print(f'{$t1 - $t0:.2f}')")
    if [ "$status" -eq 0 ]; then echo "-> PASS (${secs} s wall)"; else echo "-> FAIL (exit $status, ${secs} s wall)"; fail=1; fi
  done
  echo
  if [ "$fail" -ne 0 ]; then echo "RESULT: at least one step failed"
  elif [ -n "$skipped" ]; then echo "RESULT: every step that ran passed; skipped:$skipped"
  else echo "RESULT: all steps passed"; fi
} > "$out" 2>&1
cat "$out"
if [ "${EVIDENCE:-0}" = 1 ] && [ "$fail" -eq 0 ] && [ -z "$skipped" ]; then cp "$out" "$keep"; fi
[ "$fail" -eq 0 ] && [ -n "$skipped" ] && exit 3
exit "$fail"
