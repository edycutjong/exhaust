#!/bin/sh
# Feasibility probes for the Fe 26.6.0 compile-time explorer; prints a transcript.
# Every probe runs in a scratch copy of the committed ingot (git archive HEAD); src/ is never modified.
# Usage: sh bench/probes.sh > evidence/probes-$(date -u +%Y-%m-%d).txt
# evidence/probes-2026-11-15.txt ran on the P1a code; P1b leaned step() (section 5 limits moved, see evidence/budget.md).
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
pr="$root/bench/probes/feasibility"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
now() { python3 -c 'import time; print(time.time())'; }
secs() { python3 -c "print(round($2 - $1, 2))"; }
fresh() { rm -rf "$tmp/ingot"; mkdir "$tmp/ingot"; git -C "$root" archive HEAD | tar -x -C "$tmp/ingot"; }
limit_or_value() { grep -E 'step limit|left:' | head -1 | sed 's/^ *//'; }
timed() { s=$(now); (cd "$tmp/ingot" && "$@" > "$tmp/last.txt" 2>&1); ec=$?; e=$(now); echo "exit $ec, $(secs $s $e) s"; }

echo "# Feasibility probes, $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "commit: $(git rev-parse --short HEAD) · $(fe --version) · $(uname -sm) · $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p)"

echo; echo "## 1. green build and tests, three runs each (wall time includes compilation)"
fresh
for i in 1 2 3; do echo "fe build run $i: $(timed fe build)"; done
for i in 1 2 3; do echo "fe test run $i: $(timed fe test)"; done
tail -1 "$tmp/last.txt"
for i in 1 2 3; do echo "fe test --backend native run $i: $(timed fe test --backend native)"; done
tail -1 "$tmp/last.txt"

echo; echo "## 2. bug flip: demo/refund-after-release.patch, three runs, then the revert"
fresh; (cd "$tmp/ingot" && git init -q && git apply "$root/demo/refund-after-release.patch")
for i in 1 2 3; do echo "fe build run $i: $(timed fe build)"; done
grep -E 'error\[|assertion message|left:|static_assert\(counterexample' "$tmp/last.txt"
(cd "$tmp/ingot" && git apply -R "$root/demo/refund-after-release.patch")
echo "after the revert: $(timed fe build), error count $(grep -c 'error\[' "$tmp/last.txt")"

echo; echo "## 3. array initialisation: a const fn that only builds [false; N]"
for n in 900000 1100000; do
  sed "s/__N__/$n/" "$pr/array_init.fe.tmpl" > "$tmp/a.fe"
  r=$(fe build "$tmp/a.fe" 2>&1 | grep -E 'error\[3-0026\]' | head -1)
  echo "N=$n: ${r:-fits the step limit}"
done

echo; echo "## 4. budget scope: one static_assert per search vs consts that reference other consts"
fresh; printf 'static_assert(explore(19) == 609)\nstatic_assert(explore(19) == 609)\n' >> "$tmp/ingot/src/escrow_explore.fe"
echo "two more separate static_assert(explore(19) == 609): error count $(cd "$tmp/ingot" && fe build 2>&1 | grep -c 'error\[')"
fresh; printf 'const FIRST: usize = explore(19)\nconst SECOND: usize = explore(19)\nstatic_assert(FIRST == 609 && SECOND == 609)\n' >> "$tmp/ingot/src/escrow_explore.fe"
echo "two consts in one static_assert: $(cd "$tmp/ingot" && fe build 2>&1 | limit_or_value)"

echo; echo "## 5. capacity limits with every invariant checked (one static_assert each)"
for q in "explore(19)" "explore(20)" "explore(21)" "counterexample(18)" "counterexample(19)" "counterexample(20)" "counterexample(21)"; do
  fresh; echo "static_assert($q == 12345)" >> "$tmp/ingot/src/escrow_explore.fe"
  echo "$q: $(cd "$tmp/ingot" && fe build 2>&1 | limit_or_value)"
done

echo; echo "## 6. labeled-edge hash in u128 (Fe) vs the tuple model (Python)"
for c in 2 19 21; do
  fresh; cp "$pr/edges_hash.fe" "$tmp/ingot/src/hashprobe.fe"; echo "static_assert(edges_hash($c) == 1)" >> "$tmp/ingot/src/hashprobe.fe"
  echo "Fe C=$c: $(cd "$tmp/ingot" && fe build 2>&1 | grep -A4 'edges_hash' | limit_or_value)"
done
echo "tuple model:"; python3 -I "$pr/tuple_model.py" 2 17 19 21

echo; echo "## 7. generated edge table: step() vs every (state, action) attempt, both backends"
for c in 19 21; do
  fresh; rows=$(python3 -I "$pr/tuple_model.py" --table $c "$tmp/ingot/src/probe_table.fe")
  r=$(timed fe test --filter probe_oracle); r1=$(grep -E 'PASS|FAIL' "$tmp/last.txt" | head -1)
  r2=$(timed fe test --backend native --filter probe_oracle); r3=$(grep -E 'PASS|FAIL' "$tmp/last.txt" | head -1)
  echo "C=$c rows=$rows · sonatina: $r1 ($r) · native: $r3 ($r2)"
done
fresh; python3 -I "$pr/tuple_model.py" --table 21 "$tmp/ingot/src/probe_table.fe" >/dev/null
sed -i.bak 's/^const OKS: \[u32; ROWS\] = \[1,/const OKS: [u32; ROWS] = [0,/' "$tmp/ingot/src/probe_table.fe"
echo "C=21 with the first row's ok flag flipped: $(cd "$tmp/ingot" && fe test --filter probe_oracle 2>&1 | grep -E 'PASS|FAIL' | head -1)"

echo; echo "## 8. fe test at scale: 1,008 deployments and 50,400 calls in one Sonatina test"
fresh; cp "$pr/harness_load.fe" "$tmp/ingot/src/probe_load.fe"
r=$(timed fe test --filter probe_harness)
echo "$(grep -E 'PASS|FAIL' "$tmp/last.txt" | head -1) ($r)"

echo; echo "## 9. native executable that prints"
rm -rf "$tmp/np"; cp -R "$pr/native_print" "$tmp/np"
(cd "$tmp/np" && fe build --backend native --out-dir out >/dev/null 2>&1 && ./out/native_print; echo "exit status: $?")

echo; echo "## 10. const generic array size"
echo "error count: $(fe build "$pr/const_generic.fe" 2>&1 | grep -c 'error\[')"

echo; echo "## 11. negative checks of the checker"
fresh; python3 - "$tmp/ingot/src/escrow.fe" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
i = s.index('Action::Release =>'); j = s.index('let e = s.escrow - 1', i)
open(p, 'w').write(s[:j] + 'let e = s.escrow' + s[j + len('let e = s.escrow - 1'):])
PY
echo "(i) Release keeps its unit:"; (cd "$tmp/ingot" && fe build 2>&1 | grep -E 'assertion message|left:')
fresh; sed -i.bak 's/        st.buyer = n.s.buyer/        st.buyer = n.s.seller/' "$tmp/ingot/src/escrow_contract.fe"
echo "(ii) adapter stores seller into the buyer slot: fe build error count $(cd "$tmp/ingot" && fe build 2>&1 | grep -c 'error\[')"
(cd "$tmp/ingot" && fe test 2>&1 | grep -E 'FAIL|result')
fresh; echo "(iii) fe test --filter gas:"; (cd "$tmp/ingot" && fe test --filter gas 2>&1 | grep -E 'PASS|FAIL|result')
