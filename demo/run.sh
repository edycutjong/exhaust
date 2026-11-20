#!/bin/sh
# The 20-second demo. Shell + fe only (no python). Works on temp copies; the clone is never modified.
#   1. fe build on the real ingot: the compile-time search passes.
#   2. A one-line bug in the Refund guard (demo/refund-after-release.patch).
#   3. fe build again: the compiler names the broken invariant and prints the attack as digits.
#   4. The digits decoded, then replayed: the patched contract pays twice; the real contract refuses the Refund.
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
legend() {
  for d in $(echo "$1" | sed 's/./& /g'); do
    case $d in 1) printf 'Deposit ' ;; 2) printf 'Lock ' ;; 3) printf 'Release ' ;; 4) printf 'Refund ' ;; 5) printf 'Dispute ' ;; esac
  done
  echo
}
for d in ok bug replay; do mkdir "$work/$d" && cp -R "$root/fe.toml" "$root/src" "$work/$d/"; done

pin=$(grep -o 'pub const STATES: usize = [0-9]*' "$root/src/escrow_explore.fe" | grep -o '[0-9]*$')
cap=$(grep -o 'pub const CAP: u32 = [0-9]*' "$root/src/escrow.fe" | grep -o '[0-9]*$')
echo "== 1. fe build (the escrow, every reachable state at capacity $cap checked at compile time)"
if (cd "$work/ok" && fe build > out.txt 2>&1); then
  echo "   build OK: static_assert(explore(CAP) == STATES) held, STATES = $pin, every invariant held on every reachable state and edge"
else
  echo "   unexpected: the unpatched build failed"; cat "$work/ok/out.txt"; exit 1
fi

echo
echo "== 2. the bug: one line in the Refund guard (demo/refund-after-release.patch)"
grep -E '^[-+] ' "$root/demo/refund-after-release.patch" | sed 's/^\([-+]\) */   \1 /'
patch -s -d "$work/bug" -p1 < "$root/demo/refund-after-release.patch"

echo
echo "== 3. fe build again"
if (cd "$work/bug" && fe build > out.txt 2>&1); then
  echo "   unexpected: the patched build passed"; exit 1
fi
grep -E '^error\[|assertion message|left:' "$work/bug/out.txt" | sed 's/^ */   /'
digits=$(grep -o 'left: `[0-9]*`' "$work/bug/out.txt" | head -1 | grep -o '[0-9][0-9]*')
echo "   -> build FAILED (as it must)"

echo
echo "== 4. the counterexample $digits, decoded (1 Deposit . 2 Lock . 3 Release . 4 Refund . 5 Dispute)"
printf '   '; legend "$digits"
# Gate-stripped copy: the compile-time pins removed so the PATCHED contract can be built and run on Sonatina.
patch -s -d "$work/replay" -p1 < "$root/demo/refund-after-release.patch"
sed -i.bak '/^\/\/ ---- pins/,$d' "$work/replay/src/escrow_explore.fe" && rm "$work/replay/src/escrow_explore.fe.bak"
cp "$root/demo/attack_replay.fe" "$work/replay/src/"
echo "   patched contract (search removed), fe test --filter test_attack_patched_replay:"
r=$(cd "$work/replay" && fe test --filter test_attack_patched_replay 2>&1 | grep -E '^(PASS|FAIL)')
echo "     $r"
case $r in PASS*) echo "     -> all five calls accepted; the seller AND the buyer were paid" ;; *) echo "     unexpected result"; exit 1 ;; esac
echo "   real contract, fe test --filter attack:"
r=$(cd "$work/ok" && fe test --filter attack 2>&1 | grep -E '^(PASS|FAIL)')
echo "     $r"
case $r in PASS*) echo "     -> the first four calls accepted, the Refund refused, storage unchanged" ;; *) echo "     unexpected result"; exit 1 ;; esac
