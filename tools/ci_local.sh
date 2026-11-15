#!/bin/sh
# Runs the CI workflow's steps locally and writes a transcript to evidence/ci-local-<date>.txt.
# Usage: sh tools/ci_local.sh            (from the repository root)
set -u
cd "$(dirname "$0")/.."
out="evidence/ci-local-$(date -u +%Y-%m-%d).txt"
mkdir -p evidence
fail=0
{
  echo "# CI steps run locally, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo "cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2)"
  for step in "fe fmt --check" "fe check" "fe build" "fe test" "fe test --backend native"; do
    echo
    echo "## $step"
    if $step 2>&1 | grep -v '^Wrote '; then :; fi
    # re-run for the exit status without the filter
    if $step >/dev/null 2>&1; then echo "-> PASS"; else echo "-> FAIL"; fail=1; fi
  done
  echo
  if [ "$fail" -eq 0 ]; then echo "RESULT: all steps passed"; else echo "RESULT: at least one step failed"; fi
} > "$out" 2>&1
cat "$out"
exit "$fail"
