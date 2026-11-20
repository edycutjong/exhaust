#!/bin/sh
# Real terminal transcripts for the landing page, deck, README and video: the green run and one failing `fe build` per demo
# bug, each on a fresh temp copy (the working tree is never modified). Writes evidence/transcript-*.txt (plain text, no colour).
#   sh tools/transcripts.sh
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
commit=$(git rev-parse --short HEAD)
head() {
  echo "# $1"
  echo "# $(date -u '+%Y-%m-%d %H:%M UTC') · commit $commit · $(fe --version) · $(uname -sm)"
  echo "# \$ $2"
  echo
}
# build <dir>: `fe build` in <dir>, output with the temp directory stripped from the "Wrote" lines, then the exit status.
build() { (cd "$1" && fe --color never build > build.out 2>&1); rc=$?; sed 's#^Wrote .*/out/#Wrote out/#' "$1/build.out"; echo "exit status: $rc"; }
copy() { d=$(mktemp -d "$work/c.XXXXXX"); cp -R fe.toml src "$d"/; echo "$d"; }

d=$(copy)
{
  head "green: the unpatched ingot" "fe --color never build"
  build "$d"
} > evidence/transcript-pass.txt

grep -v '^#' demo/bugs.tsv | while IFS="	" read -r patch inv digits kind; do
  name=$(basename "$patch" .patch)
  d=$(copy)
  patch -s -d "$d" -p1 < "$patch" || { echo "patch failed: $patch" >&2; exit 1; }
  {
    head "fail: $name (names '$inv', prints $digits)" "patch -p1 < $patch && fe --color never build"
    build "$d"
  } > "evidence/transcript-fail-$name.txt"
  grep -q "invariant '$inv' broken" "evidence/transcript-fail-$name.txt" || { echo "FAIL: $name does not name '$inv'" >&2; exit 1; }
  grep -q "left: \`$digits\`" "evidence/transcript-fail-$name.txt" || { echo "FAIL: $name does not print $digits" >&2; exit 1; }
  echo "wrote evidence/transcript-fail-$name.txt"
done

# The native trace of the headline bug, by action name.
{
  head "native trace of refund-after-release, by action name" "sh tools/trace.sh demo/refund-after-release.patch"
  sh tools/trace.sh demo/refund-after-release.patch 2>&1; echo "exit status: $?"
} > evidence/transcript-trace-refund-after-release.txt
echo "wrote evidence/transcript-pass.txt and evidence/transcript-trace-refund-after-release.txt"
