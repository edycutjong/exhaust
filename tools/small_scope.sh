#!/bin/sh
# Small-scope check with the independent oracle: for every demo bug, the smallest configuration at which
# tools/ref_model.py already finds the violation (escrow: capacity 1..21; vault: balance B 1..10 at the checked
# timelock T = 3, then timelock T 1..3 at B = 10). Usage: sh tools/small_scope.sh > evidence/small-scope.txt
set -eu
cd "$(dirname "$0")/.."
echo "# Small-scope check (oracle tools/ref_model.py), $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "commit: $(git rev-parse HEAD)"
echo "python: $(python3 --version 2>&1)"
echo "uname: $(uname -sm)"
echo
echo "## Escrow: smallest capacity at which each bug's invariant breaks (checked capacity C = 21)"
for bug in refund-after-release settle-early mint-release cap-off-by-one; do
  c=1; hit=""
  while [ $c -le 21 ]; do
    out=$(python3 -I tools/ref_model.py --bug "$bug" --cap $c || true)
    case "$out" in *"no violation"*) c=$((c + 1)) ;; *) hit=$out; break ;; esac
  done
  echo "${hit:-$bug: no violation at any capacity 1..21}"
done
echo
echo "## Vault: smallest balance B at the checked timelock T = 3, then smallest T at B = 10 (checked: B = 10, T = 3)"
for bug in vault-approve-twice vault-execute-early vault-pay-twice vault-cancel-pays vault-execute-unguarded; do
  b=1; hit=""
  while [ $b -le 10 ]; do
    out=$(python3 -I tools/ref_model.py --bug "$bug" --b $b --t 3 || true)
    case "$out" in *"no violation"*) b=$((b + 1)) ;; *) hit=$out; break ;; esac
  done
  echo "${hit:-$bug: no violation at B 1..10, T = 3}"
  t=1; hit=""
  while [ $t -le 3 ]; do
    out=$(python3 -I tools/ref_model.py --bug "$bug" --b 10 --t $t || true)
    case "$out" in *"no violation"*) t=$((t + 1)) ;; *) hit=$out; break ;; esac
  done
  echo "${hit:-$bug: no violation at T 1..3, B = 10}"
done
