#!/bin/sh
# Re-runs the P1a probes and prints a transcript (used for evidence/p1a-probes-<date>.txt).
# Every probe that needs the ingot runs in a scratch copy; src/ is never modified.
# Usage: sh bench/p1a_probes.sh > evidence/p1a-probes-$(date -u +%Y-%m-%d).txt
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
pr="$root/bench/probes/p1a"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
now() { python3 -c 'import time; print(time.time())'; }
secs() { python3 -c "print(round($2 - $1, 2))"; }
fresh() { rm -rf "$tmp/ingot"; mkdir "$tmp/ingot"; git -C "$root" archive HEAD | tar -x -C "$tmp/ingot"; }
limit_or_value() { grep -E 'step limit|left:' | head -1 | sed 's/^ *//'; }

echo "# P1a probes, $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "commit: $(git rev-parse --short HEAD) · $(fe --version) · $(uname -sm) · $(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p)"

echo; echo "## 3. array initialisation: a const fn that only builds [false; N]"
for n in 900000 1100000; do
  sed "s/__N__/$n/" "$pr/array_init.fe.tmpl" > "$tmp/a.fe"
  r=$(fe build "$tmp/a.fe" 2>&1 | grep -E 'error\[3-0026\]' | head -1)
  echo "N=$n: ${r:-fits the step limit}"
done

echo; echo "## 7. capacity limits with every invariant checked (one static_assert each, scratch copy)"
for q in "explore(19)" "explore(20)" "explore(21)" "counterexample(18)" "counterexample(19)"; do
  fresh; echo "static_assert($q == 12345)" >> "$tmp/ingot/src/escrow_explore.fe"
  echo "$q: $(cd "$tmp/ingot" && fe build 2>&1 | limit_or_value)"
done

echo; echo "## 9. labeled-edge hash in u128 (Fe) vs the tuple model (Python)"
for c in 2 19 21; do
  fresh; cp "$pr/edges_hash.fe" "$tmp/ingot/src/hashprobe.fe"; echo "static_assert(edges_hash($c) == 1)" >> "$tmp/ingot/src/hashprobe.fe"
  echo "Fe C=$c: $(cd "$tmp/ingot" && fe build 2>&1 | grep -A4 'edges_hash' | limit_or_value)"
done
echo "tuple model:"; python3 -I "$pr/tuple_model.py" 2 17 19 21

echo; echo "## 8. generated oracle edge table (test in a scratch copy, both backends)"
for c in 19 21; do
  fresh; rows=$(python3 -I "$pr/tuple_model.py" --table $c "$tmp/ingot/src/probe_table.fe")
  s=$(now); r=$(cd "$tmp/ingot" && fe test --filter probe_oracle 2>&1 | grep -E 'PASS|FAIL' | head -1); e=$(now)
  s2=$(now); r2=$(cd "$tmp/ingot" && fe test --backend native --filter probe_oracle 2>&1 | grep -E 'PASS|FAIL' | head -1); e2=$(now)
  echo "C=$c rows=$rows sonatina: $r (wall $(secs $s $e) s) · native: $r2 (wall $(secs $s2 $e2) s)"
done
fresh; python3 -I "$pr/tuple_model.py" --table 21 "$tmp/ingot/src/probe_table.fe" >/dev/null
sed -i.bak 's/^const OKS: \[u32; ROWS\] = \[1,/const OKS: [u32; ROWS] = [0,/' "$tmp/ingot/src/probe_table.fe"
echo "C=21 with the first row's ok flag flipped: $(cd "$tmp/ingot" && fe test --filter probe_oracle 2>&1 | grep -E 'PASS|FAIL' | head -1)"

echo; echo "## 4. fe test harness at the differential's scale (1,008 deployments, 50,400 calls)"
fresh; cp "$pr/harness_load.fe" "$tmp/ingot/src/probe_load.fe"
s=$(now); r=$(cd "$tmp/ingot" && fe test --filter probe_harness 2>&1 | grep -E 'PASS|FAIL' | head -1); e=$(now)
echo "$r (fe test wall incl. compile $(secs $s $e) s)"

echo; echo "## a. native executable that prints"
rm -rf "$tmp/np"; cp -R "$pr/native_print" "$tmp/np"
(cd "$tmp/np" && fe build --backend native --out-dir out >/dev/null 2>&1 && ./out/native_print; echo "exit status: $?")

echo; echo "## b. const generic array size"
r=$(fe build "$pr/const_generic.fe" 2>&1 | grep -c 'error\[')
echo "error count: $r"

echo; echo "## 1 + timing. bug flip (demo/refund-after-release.patch) in a scratch copy, three runs"
fresh; (cd "$tmp/ingot" && git init -q && git apply "$root/demo/refund-after-release.patch")
for i in 1 2 3; do
  s=$(now); out=$(cd "$tmp/ingot" && fe build 2>&1); ec=$?; e=$(now)
  echo "run $i: exit $ec, $(secs $s $e) s"
done
echo "$out" | grep -E 'error\[|assertion message|left:'

echo; echo "## 10. negative checks of the checker (scratch copies)"
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
echo "(iii) fe test --filter gas:"; fe test --filter gas 2>&1 | grep -E 'PASS|FAIL|result'
