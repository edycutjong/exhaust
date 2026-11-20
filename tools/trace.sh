#!/bin/sh
# Native trace printer. Prints the shortest counterexample of the escrow (capacity 19) and of the vault (B = 10, T = 3)
# by action name, with the state after each step. With a patch, the printer runs on a temp copy of the ingot with that
# patch applied and its compile-time pins removed (a patched model fails `fe build` by design; the pins are what stop it).
#   sh tools/trace.sh                                   the unpatched models: no counterexample, exit 0
#   sh tools/trace.sh demo/refund-after-release.patch   the attack `fe build` names, by action name: exit 1
# Needs a native toolchain for `fe build --backend native` (run on macOS arm64; Linux x86-64 needs a C linker `cc` and has not been run).
set -u
cd "$(dirname "$0")/.."
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -R fe.toml src tools "$work"/
rm -rf "$work/tools/trace/out"
if [ $# -gt 0 ]; then
  for p in "$@"; do
    patch -s -d "$work" -p1 < "$root/$p" || { echo "patch failed: $p" >&2; exit 2; }
  done
  for f in escrow_explore vault_explore; do
    sed -i.bak '/^\/\/ ---- pins/,$d' "$work/src/$f.fe" && rm "$work/src/$f.fe.bak"
  done
fi
(cd "$work/tools/trace" && fe build --backend native --out-dir "$work/out" > "$work/build.txt" 2>&1) \
  || { cat "$work/build.txt" >&2; exit 2; }
"$work/out/exhaust_trace"
