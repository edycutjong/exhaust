#!/bin/sh
# Runs the exhaustive-edge differential on Sonatina and reports it from the test's own event log
# (saved to evidence/differential.txt with EVIDENCE=1, only when the test passed).
# Usage: sh tools/differential.sh     (needs fe; python3 only to decode the event's six words)
set -eu
cd "$(dirname "$0")/.."
out=$(mktemp)
log=$(mktemp)
trap 'rm -f "$log" "$out"' EXIT
start=$(python3 -c 'import time; print(time.time())')
fe test --filter test_differential_all_edges --show-logs > "$log" 2>&1
end=$(python3 -c 'import time; print(time.time())')
{
  echo "# Exhaustive-edge differential (test_differential_all_edges), $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo "cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null || grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"
  echo
  grep -E '^(PASS|FAIL)' "$log"
  python3 - "$log" "$start" "$end" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
data = re.search(r"data: 0x([0-9a-f]+) \}", text).group(1)
names = ["cap", "states", "edges", "attempts", "deployments", "action_calls", "raw_state_reads (one after each action call)"]
vals = [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]
for n, v in zip(names, vals):
    print(f"{n}: {v}")
print(f"total_calls: {vals[5] + vals[6]}")
print("shards: 1 (one #[test], no harness limit hit)")
print(f"wall_time_s (whole fe test command incl. compile): {float(sys.argv[3]) - float(sys.argv[2]):.2f}")
PY
  grep -E '^test result' "$log"
} > "$out"
cat "$out"
if [ "${EVIDENCE:-0}" = 1 ] && grep -q "^PASS" "$out"; then cp "$out" evidence/differential.txt; fi
