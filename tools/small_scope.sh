#!/bin/sh
# Small-scope check with the independent oracle: for every demo bug in demo/bugs.tsv, the smallest configuration at
# which tools/ref_model.py already finds the violation (escrow: capacity 1..21; vault: balance B 1..10 at the checked
# timelock T = 3, then timelock T 1..3 at B = 10). Usage: sh tools/small_scope.sh > evidence/small-scope.txt
# Exit 1 if a bug shows no violation even at the checked configuration; exit 2 if the oracle crashes (a traceback
# is never counted as a hit).
set -eu
cd "$(dirname "$0")/.."
echo "# Small-scope check (oracle tools/ref_model.py), $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "commit: $(git rev-parse HEAD)"
echo "python: $(python3 --version 2>&1)"
echo "uname: $(uname -sm)"
missing=0

# probe <oracle args...>: sets $out and returns 0 on a violation, 1 on "no violation found"; exits 2 on anything else.
probe() {
  rc=0; out=$(python3 -I tools/ref_model.py "$@" 2>&1) || rc=$?
  case "$rc:$out" in
    0:*"invariant '"*) return 0 ;;
    1:*"no violation found") return 1 ;;
    *) echo "ORACLE ERROR (exit $rc) for: $*" >&2; echo "$out" >&2; exit 2 ;;
  esac
}
bugs() { grep -v '^#' demo/bugs.tsv | awk -F '\t' -v want="$1" '($4 == "vault") == (want == "vault") { sub(/^demo\//, "", $1); sub(/\.patch$/, "", $1); print $1 }'; }

echo
echo "## Escrow: smallest capacity at which each bug's invariant breaks (checked capacity C = 21)"
for bug in $(bugs escrow); do
  c=1; hit=""
  while [ $c -le 21 ]; do
    if probe --bug "$bug" --cap $c; then hit=$out; break; fi
    c=$((c + 1))
  done
  [ -n "$hit" ] || missing=1
  echo "${hit:-$bug: no violation at any capacity 1..21}"
done
echo
echo "## Vault: smallest balance B at the checked timelock T = 3, then smallest T at B = 10 (checked: B = 10, T = 3)"
for bug in $(bugs vault); do
  b=1; hit=""
  while [ $b -le 10 ]; do
    if probe --bug "$bug" --b $b --t 3; then hit=$out; break; fi
    b=$((b + 1))
  done
  [ -n "$hit" ] || missing=1
  echo "${hit:-$bug: no violation at B 1..10, T = 3}"
  t=1; hit=""
  while [ $t -le 3 ]; do
    if probe --bug "$bug" --b 10 --t $t; then hit=$out; break; fi
    t=$((t + 1))
  done
  [ -n "$hit" ] || missing=1
  echo "${hit:-$bug: no violation at T 1..3, B = 10}"
done
exit $missing
