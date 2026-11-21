#!/bin/sh
# Transition coverage. Fe 26.6.0 ships no line-coverage tool, so the measurable coverage here is over the model's
# transitions: how many of the oracle's reachable edges the exhaustive-edge differential replayed through the DEPLOYED
# contract (evm.call). The per-edge compare (`ok` and the stored state against step() after every call) happens inside
# the Fe tests, which must pass; this script then checks that the replayed COUNTS equal the oracle's reachable counts.
# The denominators come from the independent Python oracle (tools/ref_model.py), the numerators from the tests' own
# event logs. Exits 1 unless every numerator equals its (non-zero) denominator.
# Usage: sh tools/transition_coverage.sh     (EVIDENCE=1 saves evidence/transition-coverage.txt when it passes)
set -eu
cd "$(dirname "$0")/.."
log=$(mktemp)
out=$(mktemp)
trap 'rm -f "$log" "$out"' EXIT
rc=0
fe test --filter test_differential_all_edges --show-logs > "$log" 2>&1 || rc=$?
fe test --filter test_vault_differential --show-logs >> "$log" 2>&1 || rc=$?
if [ "$rc" -ne 0 ]; then cat "$log"; echo "differential tests FAILED (exit $rc)"; exit 1; fi
rc=0
python3 -I - "$log" > "$out" <<'PY' || rc=$?
import re, sys
sys.path.insert(0, "tools")
import ref_model as m

text = open(sys.argv[1]).read()
events = [[int(h[i:i + 64], 16) for i in range(0, len(h), 64)] for h in re.findall(r"data: 0x([0-9a-f]+) \}", text)]
escs = [e for e in events if len(e) == 7]              # DifferentialRun: cap states edges attempts deployments calls reads
assert len(escs) == 1, "expected exactly one escrow differential event, got %d" % len(escs)
esc = escs[0]
vlt = [e for e in events if len(e) == 6]               # VaultDifferentialRun: ready states edges attempts deployments calls
# The replay must have run at the checked configuration, so the denominators cannot shrink with it.
cap = int(re.search(r"pub const CAP: u32 = (\d+)", open("src/escrow.fe").read()).group(1))
assert esc[0] == cap, "escrow differential ran at C=%d, the checked capacity is CAP = %d (src/escrow.fe)" % (esc[0], cap)
assert len(vlt) == 2 and sorted(v[0] for v in vlt) == [0, 1], "expected one vault run with the lock passed and one without"
rows, ok = [], True
r = m.search(esc[0])
rows.append(("escrow (C=%d), accepted edges" % esc[0], esc[2], r["edges"]))
rows.append(("escrow (C=%d), attempts (accepted + rejected)" % esc[0], esc[3], r["attempts"]))
rows.append(("escrow (C=%d), states reached" % esc[0], esc[1], r["states"]))
for v in vlt:
    g = m.vcontract_graph(10, 3, bool(v[0]))
    tag = "lock passed" if v[0] else "lock never passes"
    rows.append(("vault contract graph B=10 T=3 (%s), accepted edges" % tag, v[2], g["edges"]))
    rows.append(("vault contract graph B=10 T=3 (%s), attempts" % tag, v[3], g["attempts"]))
    rows.append(("vault contract graph B=10 T=3 (%s), states reached" % tag, v[1], g["states"]))
print("| transition set | replayed on the EVM | oracle reachable | covered |")
print("|---|---:|---:|---:|")
for name, got, want in rows:
    match = want != 0 and got == want   # a zero denominator is a gap, never 100%
    ok &= match
    print("| %s | %d | %d | %s |" % (name, got, want, "100%" if match else "gap" if want == 0 else "%.1f%%" % (100.0 * got / want)))
print()
print("Scope: the escrow's contract graph equals its model (%d states). The vault's contract graph is a subset of its %d-state model" % (esc[1], m.vsearch(10, 3)["states"]))
print("(the harness can neither tick the clock nor change the caller), so its %s states are what the deployed handlers can reach;" % " + ".join(str(v[1]) for v in vlt))
print("the model-level vault search is exercised by the compile-time and runtime explorers, not by this replay. Its denominators")
print("are the oracle's contract-graph counts, so a vault match shows the replay reached everything the oracle says is reachable there.")
print()
print("RESULT: " + ("the replayed counts equal the oracle's reachable counts, and every replayed call matched step() in the tests (escrow: its full model graph; vault: the deployed handlers' contract graph)" if ok else "COVERAGE GAP"))
sys.exit(0 if ok else 1)
PY
{
  echo "# Transition coverage, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo
  echo "Line coverage: none. Fe 26.6.0 has no coverage tool (checked: \`fe --help\` lists no coverage command)."
  echo
  cat "$out"
} > "$out.full"
cat "$out.full"
if [ "${EVIDENCE:-0}" = 1 ] && [ "$rc" -eq 0 ]; then cp "$out.full" evidence/transition-coverage.txt; fi
rm -f "$out.full"
exit "$rc"
