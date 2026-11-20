#!/bin/sh
# Clean-clone reproduction on Linux x86-64 in Docker (ubuntu:24.04, linux/amd64).
# Usage: sh tools/repro_linux.sh [git-url]      default: a bundle of this checkout's HEAD
# Steps inside the container: clone → feup at tag v26.6.0 → fe fmt --check → fe build → fe test →
# fe test --backend native without a C linker, then with gcc → apply demo/refund-after-release.patch → fe build (must fail).
set -eu
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
src="${1:-}"
if [ -z "$src" ]; then git bundle create "$work/repo.bundle" HEAD >/dev/null 2>&1; src=/w/repo.bundle; fi
cat > "$work/inner.sh" <<'INNER'
set -u
mark() { if [ "$1" -eq 0 ]; then echo "-> PASS"; else echo "-> FAIL (exit $1)"; fi; }
apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq curl git ca-certificates patch >/dev/null 2>&1
t0=$(date +%s)
git -c advice.detachedHead=false clone -q "$SRC" exhaust && cd exhaust && echo "commit: $(git rev-parse HEAD)"
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/v26.6.0/feup/feup.sh | bash -s -- --version v26.6.0 --no-modify-path >/dev/null 2>&1
export PATH=$HOME/.fe/bin:$PATH
echo "fe: $(fe --version)"; echo "uname: $(uname -sm)"
echo "== fe fmt --check"; fe fmt --check; mark $?
echo "== fe build"; fe build > /tmp/b.txt 2>&1; ec=$?; grep -c 'error\[' /tmp/b.txt | sed 's/^/error count: /'; mark $ec
echo "== fe test"; fe test > /tmp/t.txt 2>&1; ec=$?; tail -1 /tmp/t.txt; mark $ec
echo "== fe test --backend native (no C linker installed)"; fe test --backend native > /tmp/n0.txt 2>&1; ec=$?; grep -E 'ERROR|result' /tmp/n0.txt | head -2; mark $ec
apt-get install -y -qq gcc libc6-dev >/dev/null 2>&1
echo "== fe test --backend native (after apt-get install gcc libc6-dev)"; fe test --backend native > /tmp/n1.txt 2>&1; ec=$?; tail -1 /tmp/n1.txt; mark $ec
echo "== sh demo/run.sh (the README demo: green build, bug patch red, replays)"; sh demo/run.sh > /tmp/demo.txt 2>&1; ec=$?; grep -E "assertion message|left:|PASS|FAIL" /tmp/demo.txt; mark $ec
echo "== bug flip: git apply demo/refund-after-release.patch && fe build (must fail)"
git apply demo/refund-after-release.patch; fe build > /tmp/bug.txt 2>&1; echo "exit: $?"
grep -E 'assertion message|left:' /tmp/bug.txt
echo "seconds from clone to the red build (includes the gcc install): $(( $(date +%s) - t0 ))"
INNER
docker run --rm --platform linux/amd64 -e SRC="$src" -v "$work":/w ubuntu:24.04 sh /w/inner.sh
