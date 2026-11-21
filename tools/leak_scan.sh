#!/bin/sh
# Pre-push / pre-public scan: gitleaks over the full history, and no kitchen file tracked in this repo.
# Usage: sh tools/leak_scan.sh        (needs gitleaks; CI runs the same gitleaks scan in security.yml)
set -eu
cd "$(dirname "$0")/.."
gitleaks detect --source . --log-opts="--all" --redact
echo "gitleaks: no leaks found"
hits=$(git ls-files | grep -iE 'spec|progress|predict|radar|CLAUDE|AGENTS|\.claude|\.vercel|\.env$|pem$' | grep -vE '^(src/oracle_edges\.fe)$' || true)
if [ -n "$hits" ]; then
  echo "tracked files matching the kitchen pattern (read each: a *spec* test name or a .patch is fine):"
  echo "$hits"
  exit 1
fi
echo "kitchen-file pattern: no tracked file matches"
