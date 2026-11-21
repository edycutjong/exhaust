#!/bin/sh
# X7: every demo bug must fail `fe build`, naming its invariant and printing its counterexample digits.
#   sh demo/check-bugs.sh                 bug zoo (demo/bugs.tsv)
#   sh demo/check-bugs.sh --conformance   the checker's own negative tests (conformance/expected.tsv)
# Every patch is applied to a fresh temp copy; the working tree is never modified. Exit 1 if any row disagrees.
# With EVIDENCE=1 the transcript is also saved to evidence/check-bugs.txt or evidence/conformance.txt.
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
mode=${1:-zoo}
# Every temp copy, transcript and the failure flag live under one work root, removed on exit.
case "$mode" in zoo|--conformance) ;; *) echo "usage: sh demo/check-bugs.sh [--conformance]" >&2; exit 2 ;; esac
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
flag="$work/failed"
ran="$work/rows-run"  # one line per table row executed (the rows run in a pipeline subshell, so a file counts them)

# copy <patch> <full|nohash|stripped[+file]>: prints the path of a fresh patched copy of the ingot.
copy() {
  d=$(mktemp -d "$work/copy.XXXXXX")
  cp -R "$root/fe.toml" "$root/src" "$d"/
  case "$2" in
    nohash)
      # Without the labeled-edge hash pin, so the build can reach the runtime oracle-table test.
      sed -i.bak '/fingerprint(CAP, true,/d' "$d/src/escrow_explore.fe" && rm "$d/src/escrow_explore.fe.bak"
      ;;
    stripped*)
      # Gate-stripped: drop the compile-time pins (everything from the "---- pins" marker on) so a patched
      # contract can still be built and run.
      sed -i.bak '/^\/\/ ---- pins/,$d' "$d/src/escrow_explore.fe" && rm "$d/src/escrow_explore.fe.bak"
      sed -i.bak '/^\/\/ ---- pins/,$d' "$d/src/vault_explore.fe" && rm "$d/src/vault_explore.fe.bak"
      extra=${2#stripped}
      extra=${extra#+}
      [ -n "$extra" ] && cp "$root/$extra" "$d/src/"
      ;;
  esac
  if [ -n "$1" ] && ! patch -s -d "$d" -p1 < "$root/$1" >&2; then
    echo "patch failed: $1" >&2; echo 1 > "$flag"
  fi
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
  out="$work/transcript.txt"; keep=evidence/conformance.txt
  {
    header "Conformance: the checker's own negative tests (conformance/expected.tsv)"
    grep -v '^#' conformance/expected.tsv | while IFS="	" read -r id patch where cmd want expect; do
      echo x >> "$ran"
      d=$(copy "$patch" "$where")
      log="$d/out.txt"
      (cd "$d" && $cmd > "$log" 2>&1)
      got=$?
      ok=1
      [ "$got" -eq "$want" ] || ok=0
      rest=$expect
      while [ -n "$rest" ]; do
        pat=${rest%%;;*}
        case $pat in
          !*) ! grep -Eq -- "${pat#!}" "$log" || ok=0 ;;  # "!regex": must NOT appear
          *) grep -Eq -- "$pat" "$log" || ok=0 ;;
        esac
        [ "$pat" = "$rest" ] && rest="" || rest=${rest#*;;}
      done
      if [ "$ok" -eq 1 ]; then r=PASS; else r=FAIL; echo 1 > "$flag"; fi
      echo "$r  $id  $patch  [$where]  \`$cmd\` exit $got (want $want)  expect: $expect"
    done
  } > "$out" 2>&1
else
  out="$work/transcript.txt"; keep=evidence/check-bugs.txt
  {
    header "Bug zoo: every patch must fail fe build naming its invariant and printing its digits (demo/bugs.tsv)"
    d=$(copy "" full)
    (cd "$d" && fe build > out.txt 2>&1) && echo "PASS  baseline: unpatched fe build exit 0" \
      || { echo "FAIL  baseline: unpatched fe build failed"; echo 1 > "$flag"; }
    echo
    echo "patch | fe build exit | invariant named | digits printed | per-handler suite (test_handler_* / test_vault_handler_*) | scripted contract run (test_contract_matches_step / test_vault_contract_matches_vstep)"
    grep -v '^#' demo/bugs.tsv | while IFS="	" read -r patch inv digits kind; do
      echo x >> "$ran"
      d=$(copy "$patch" full)
      (cd "$d" && fe build > out.txt 2>&1)
      st=$?
      named=no; grep -q "invariant '$inv' broken" "$d/out.txt" && named=yes
      shown=no; grep -q "left: \`$digits\`" "$d/out.txt" && shown=yes
      # Ablation (measured, not assumed): would the ordinary tests catch the same patch without the search?
      s=$(copy "$patch" stripped)
      # The vault rows (4th column "vault") use the vault's own suite.
      hf_filter=test_handler_; cf_filter=test_contract_matches_step; nh=5
      if [ "${kind:-}" = vault ]; then hf_filter=test_vault_handler_; cf_filter=test_vault_contract_matches_vstep; nh=4; fi
      (cd "$s" && fe test --filter "$hf_filter" > h.txt 2>&1); h=$?
      (cd "$s" && fe test --filter "$cf_filter" > c.txt 2>&1); c=$?
      # "caught" needs a failing test (a compile error in the copy would be a broken check, not a catch).
      hf=$(grep -c '^FAIL' "$s/h.txt"); cf=$(grep -c '^FAIL' "$s/c.txt")
      hcat=missed; [ "$h" -ne 0 ] && hcat="caught ($hf of $nh fail)"
      ccat=missed; [ "$c" -ne 0 ] && ccat=caught
      if { [ "$h" -ne 0 ] && [ "$hf" -eq 0 ]; } || { [ "$c" -ne 0 ] && [ "$cf" -eq 0 ]; }; then
        hcat="$hcat (no FAIL line: broken check)"; echo 1 > "$flag"
      fi
      r=PASS
      if [ "$st" -eq 0 ] || [ "$named" = no ] || [ "$shown" = no ]; then r=FAIL; echo 1 > "$flag"; fi
      echo "$r  $patch | exit $st | '$inv': $named | $digits: $shown | $hcat | $ccat"
      grep -E "assertion message|left:" "$d/out.txt" | sed 's/^ */      /'
    done
  } > "$out" 2>&1
fi
cat "$out"
# An empty or truncated table must not pass vacuously: every data row has to have run.
tsv=demo/bugs.tsv; [ "$mode" = "--conformance" ] && tsv=conformance/expected.tsv
rows=$(grep -v '^#' "$tsv" | grep -c .)
nran=0; [ -f "$ran" ] && nran=$(wc -l < "$ran" | tr -d ' ')
echo "rows run: $nran of $rows in $tsv"
if [ "$rows" -eq 0 ] || [ "$nran" -ne "$rows" ]; then echo "FAIL  table rows: ran $nran of $rows (an empty table is a broken check)"; echo 1 > "$flag"; fi
if [ -f "$flag" ]; then echo "RESULT: FAIL"; exit 1; fi
# Saved only from a green run, so a failing run never overwrites committed evidence.
if [ "${EVIDENCE:-0}" = 1 ]; then cp "$out" "$keep"; fi
echo "RESULT: all rows as expected"
