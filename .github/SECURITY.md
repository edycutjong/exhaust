# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| latest release and `main` | yes |

## What is in scope

exhaust is a research-grade demonstration, not audited, and its contracts are example protocols (an escrow and a 2-of-3
vault) written to be model-checked. Nothing in this repo deploys them to a live network, they hold no funds, and they must not be used with real funds. Reports we
care about: a way for a bug to pass `fe build` without a named invariant, a mismatch between `step()` and the deployed
contract, a leaked secret in the history, or a vulnerable workflow. The README's "What this does not prove" lists the
known, documented gaps.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Report it privately with GitHub's
[private vulnerability reporting](https://github.com/edycutjong/exhaust/security/advisories/new). You will get an
acknowledgment within 72 hours and a plan after triage; please allow a reasonable window to fix it before disclosing.
