#!/bin/sh
# X7: every demo bug must fail `fe build`, naming its invariant and printing its counterexample digits.
#   sh demo/check-bugs.sh                 bug zoo (demo/bugs.tsv) -> evidence/check-bugs.txt
#   sh demo/check-bugs.sh --conformance   the checker's own negative tests (conformance/expected.tsv) -> evidence/conformance.txt
# Every patch is applied to a fresh temp copy; the working tree is never modified. Exit 1 if any row disagrees.
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
mode=${1:-zoo}
tmps=""
trap 'for d in $tmps; do rm -rf "$d"; done' EXIT

# copy <patch> <full|stripped[+file]>: prints the path of a fresh patched copy of the ingot.
copy() {
  d=$(mktemp -d)
  tmps="$tmps $d"
  cp -R "$root/fe.toml" "$root/src" "$d"/
  case "$2" in
    stripped*)
      # Gate-stripped: drop the compile-time pins (everything from the "---- pins" marker on) so a patched
      # contract can still be built and run.
      sed -i.bak '/^\/\/ ---- pins/,$d' "$d/src/escrow_explore.fe" && rm "$d/src/escrow_explore.fe.bak"
      extra=${2#stripped}
      extra=${extra#+}
      [ -n "$extra" ] && cp "$root/$extra" "$d/src/"
      ;;
  esac
  [ -n "$1" ] && patch -s -d "$d" -p1 < "$root/$1"
  echo "$d"
}

header() {
  echo "# $1, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "commit: $(git rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "fe: $(fe --version)"
  echo "uname: $(uname -a)"
  echo
}

fail=0
if [ "$mode" = "--conformance" ]; then
  out=evidence/conformance.txt
  {
    header "Conformance: the checker's own negative tests (conformance/expected.tsv)"
    grep -v '^#' conformance/expected.tsv | while IFS="	" read -r id patch where cmd want expect; do
      d=$(copy "$patch" "$where")
      log="$d/out.txt"
      (cd "$d" && $cmd > "$log" 2>&1)
      got=$?
      ok=1
      [ "$got" -eq "$want" ] || ok=0
      rest=$expect
      while [ -n "$rest" ]; do
        pat=${rest%%;;*}
        grep -Eq -- "$pat" "$log" || ok=0
        [ "$pat" = "$rest" ] && rest="" || rest=${rest#*;;}
      done
      if [ "$ok" -eq 1 ]; then r=PASS; else r=FAIL; echo 1 > "$root/.check-bugs-fail"; fi
      echo "$r  $id  $patch  [$where]  \`$cmd\` exit $got (want $want)  expect: $expect"
    done
  } > "$out" 2>&1
else
  out=evidence/check-bugs.txt
  {
    header "Bug zoo: every patch must fail fe build naming its invariant and printing its digits (demo/bugs.tsv)"
    d=$(copy "" full)
    (cd "$d" && fe build > out.txt 2>&1) && echo "PASS  baseline: unpatched fe build exit 0" \
      || { echo "FAIL  baseline: unpatched fe build failed"; echo 1 > "$root/.check-bugs-fail"; }
    echo
    echo "patch | fe build exit | invariant named | digits printed | per-handler suite (test_handler_*) | spike 8-call script (test_contract_matches_step)"
    grep -v '^#' demo/bugs.tsv | while IFS="	" read -r patch inv digits; do
      d=$(copy "$patch" full)
      (cd "$d" && fe build > out.txt 2>&1)
      st=$?
      named=no; grep -q "invariant '$inv' broken" "$d/out.txt" && named=yes
      shown=no; grep -q "left: \`$digits\`" "$d/out.txt" && shown=yes
      # Ablation (measured, not assumed): would the ordinary tests catch the same patch without the search?
      s=$(copy "$patch" stripped)
      (cd "$s" && fe test --filter test_handler_ > h.txt 2>&1); h=$?
      (cd "$s" && fe test --filter test_contract_matches_step > c.txt 2>&1); c=$?
      hcat=missed; [ "$h" -ne 0 ] && hcat="caught ($(grep -c '^FAIL' "$s/h.txt") of 5 fail)"
      ccat=missed; [ "$c" -ne 0 ] && ccat=caught
      r=PASS
      if [ "$st" -eq 0 ] || [ "$named" = no ] || [ "$shown" = no ]; then r=FAIL; echo 1 > "$root/.check-bugs-fail"; fi
      echo "$r  $patch | exit $st | '$inv': $named | $digits: $shown | $hcat | $ccat"
      grep -E "assertion message|left:" "$d/out.txt" | sed 's/^ */      /'
    done
  } > "$out" 2>&1
fi
cat "$out"
if [ -f "$root/.check-bugs-fail" ]; then rm -f "$root/.check-bugs-fail"; echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: all rows as expected"
