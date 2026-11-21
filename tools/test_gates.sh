#!/bin/sh
# Regression tests for the evidence gates themselves: a gate that cannot fail proves nothing.
#   1. demo/check-bugs.sh fails on a bug table with no rows (zoo and --conformance).
#   2. tools/small_scope.sh exits 2 when the oracle crashes (an unknown bug name) instead of counting it as a hit.
# Each case runs on a temporary copy of the repository; the working tree is never modified. Exit 1 on any surprise.
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail=0
expect() { # expect <name> <wanted exit> <got exit>
  if [ "$3" -eq "$2" ]; then echo "PASS  $1 (exit $3)"; else echo "FAIL  $1 (exit $3, wanted $2)"; fail=1; fi
}
fresh() { d=$(mktemp -d "$work/copy.XXXXXX"); (cd "$root" && tar cf - --exclude ./.git --exclude ./docs --exclude ./out .) | (cd "$d" && tar xf -); echo "$d"; }

d=$(fresh); grep '^#' "$d/demo/bugs.tsv" > "$d/demo/bugs.tsv.new" && mv "$d/demo/bugs.tsv.new" "$d/demo/bugs.tsv"
sh "$d/demo/check-bugs.sh" > "$d/log" 2>&1; expect "check-bugs.sh with an empty bug table fails" 1 $?
grep -q 'ran 0 of 0' "$d/log" || { echo "FAIL  the empty-table failure names the row count"; fail=1; }

d=$(fresh); grep '^#' "$d/conformance/expected.tsv" > "$d/conformance/expected.tsv.new" && mv "$d/conformance/expected.tsv.new" "$d/conformance/expected.tsv"
sh "$d/demo/check-bugs.sh" --conformance > "$d/log" 2>&1; expect "check-bugs.sh --conformance with an empty table fails" 1 $?

d=$(fresh); printf '# header\ndemo/no-such-bug.patch\tnone\t1\n' > "$d/demo/bugs.tsv"
sh "$d/tools/small_scope.sh" > "$d/log" 2>&1; expect "small_scope.sh stops on an oracle crash" 2 $?
grep -q 'ORACLE ERROR' "$d/log" || { echo "FAIL  the crash is reported as ORACLE ERROR"; fail=1; }

if [ "$fail" -eq 0 ]; then echo "RESULT: every gate fails when it should"; else echo "RESULT: FAIL"; fi
exit "$fail"
