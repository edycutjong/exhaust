# P1c: the vault, the native trace, the benchmarks and the state graphs

Run on `fe 26.6.0 (5b3f96a)`, Darwin arm64 (Apple M1), 2026-11-21. Every number below is read from a file in `evidence/` or re-derived by the command beside it.

| What | Result | Where |
|---|---|---|
| Vault model, B = 10, T = 3 | 211 states in one `static_assert` (549,269 of 1,000,000 steps); attack printer 652,061 steps; oracle agrees (211 / 580 edges / 1,477 attempts, diameter 70) | `evidence/budget.md`, `evidence/oracle.txt` |
| Vault at other timelocks | T = 1: 131, T = 2: 171, plus the spec's baseline B = 8, T = 2: 137; each its own assert | `src/vault_explore.fe`, `evidence/oracle.txt` |
| Vault bugs | `vault-approve-twice` names `counted once`, prints `122`; `vault-execute-early` names `timelock respected`, prints `1236`; both fail `fe build` | `evidence/check-bugs.txt`, `evidence/transcript-fail-vault-*.txt` |
| Vault contract | six handlers over the shared `vstep()`; 12 vault tests incl. the differential (91 states / 250 edges with the lock passed, 9 / 21 with a lock that never passes; oracle-pinned) | `src/vault_contract.fe`, `src/vault_tests.fe`, `MODEL.md` |
| Tests | `fe test` 27 passed (Sonatina); `fe test --backend native` 10 passed | `fe test` output |
| Native trace | `tools/trace` (native executable running the Fe explorers) via `sh tools/trace.sh [patch]`, and `tools/decode-trace` (Python, digits → names) | `evidence/transcript-trace-refund-after-release.txt` |
| Benchmarks | escrow capacity sweep, step budget, shard scaling 1/2/4/8, runtime gas (EVM) and time (native), vault rows | `evidence/bench-2026-11-20.{json,md}` |
| State graphs | escrow C = 21 (736 nodes, 966 edges), vault B = 10, T = 3 (211 nodes, 580 edges), BFS depth per node, the demo bugs' attack paths | `evidence/state-graph-{escrow,vault}.json` |
| Transcripts | the green build, one failing build per bug (6), the native trace | `evidence/transcript-*.txt` |
| Cost of the port | lines, failure points, ablation | `evidence/transfer-vault.md` |

Not covered, and said so in `MODEL.md` and `evidence/transfer-vault.md`: the vault contract's caller authorization (the harness
cannot change its caller, so all three signers are one address; skipping the signer-B check is not caught), time passing between
the model's ticks (the contract has no Tick handler; a lock period is all-or-nothing), and any vault state with `0 < clock < T`.
