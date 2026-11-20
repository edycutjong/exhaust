# Architecture review fixes (2026-11-21)

Run on `fe 26.6.0 (5b3f96a)`, Darwin arm64 (Apple M1 Max). Every number below is read from a file in `evidence/` or from the
source it names. An outside architecture review of the explorer, invariants, differential, oracle and demo scripts was
checked claim by claim against this tree; these are the changes that held up.

| What changed | Why | Evidence |
|---|---|---|
| Vault invariant 10 `only execute pays` (transition): any action other than Execute leaves `bal` and `paid` unchanged | A Cancel that paid the pending unit out kept `conserved` and every state invariant and only reached states the correct vault also reaches, so the 211-state pin held and the build was green | `src/vault.fe` (`vfirst_violation`), `MODEL.md` invariant table |
| Bug V4 `demo/vault-cancel-pays.patch` | `fe build` now names `only execute pays` and prints `17` (Propose, Cancel); the native trace shows the balance drop | `evidence/check-bugs.txt`, `evidence/transcript-fail-vault-cancel-pays.txt`, `evidence/transcript-trace-vault-cancel-pays.txt` |
| Vault edge pins from the checked search: `vexplore` is `vsearch(b, t, mode)`; `vsearch(VB, VT, V_COUNT_EDGES) == 580` and `vsearch(VB, VT, V_HASH_EDGES) == 1115689132712769016`, each its own `static_assert` | A state count alone missed an explorer that never tries Cancel (still 211 states, 380 edges) | `src/vault_explore.fe`, `evidence/oracle.txt` (the Python oracle computes the same hash) |
| Conformance K7 `conformance/vault-skip-cancel.patch` | The vault's checked search stops at `a < 6`: the state pin holds, the edge pin fails with `left: 380`, no invariant is named | `evidence/conformance.txt` |
| `test_vault_identity_guards` | The vault's caller checks were never executed by a test (every deployment had the harness as all three signers). Harness as signer A only: ApproveB and ApproveC refused, nothing stored changes, ApproveA accepted. Harness as no signer: Propose refused | `src/vault_tests.fe`, `evidence/transcript-tests.txt` |
| `tools/ref_model.py --check` also compares `src/oracle_edges.fe` with the table the oracle emits now | A stale generated table would otherwise go unnoticed after an edit | `evidence/oracle.txt` (last check line) |
| Wording: escrow `conserved` bounds the total only; `two distinct approvals` is defence in depth; the counterexample digits need the bug to be reachable within C′ = 19; the step-budget resolution is one burn iteration (≈ 23 steps); the T = 1 / T = 2 vault runs are separate models, not shards; the bench wall-time spread is computed, with the load average | Each earlier sentence said more than the code or the data showed | `README.md` Limitations, `src/escrow.fe`, `MODEL.md`, `evidence/budget.md`, `evidence/bench-2026-11-20.md` |
| Test helpers `send()` / `vsend()` assert on an unknown action id | They fell through to Dispute / Cancel | `src/tests.fe`, `src/vault_tests.fe` |
| Bug V5 `demo/vault-execute-unguarded.patch`: Execute without its phase, quorum and timelock guards | Shows that `two distinct approvals`, which no single-guard bug reaches first, does fire: `fe build` names it and prints `6` | `evidence/check-bugs.txt`, `evidence/transcript-fail-vault-execute-unguarded.txt`, `evidence/oracle.txt` |
| `require()` / `vrequire()` end with an assert only an unknown invariant id reaches; `two distinct approvals` compares with `K`, not a literal 2 | An id without a message used to fall through and let the search continue; the literal would drift if `K` changed | `src/escrow_explore.fe`, `src/vault_explore.fe`, `src/vault.fe` |
| README: the vault's caller checks are adapter code (approvals per signer, Propose / Cancel by any signer, Execute by anyone), one signer can censor; the real timelock is adapter code (`now >= queued_at + lock`); the equality side of `>=` is exercised at lock 0 (a `>` there fails three tests: conformance K8, `conformance/lock-boundary-gt.patch`) | The README said the contract had no access control (true for the escrow only) and called the whole lock boundary untested | `README.md` Limitations, `src/vault_contract.fe` |

## Numbers after the change

| Check | Result | Where |
|---|---|---|
| Vault step budget | `vexplore(VB, VT)` 586,715 steps (58.7%); `vcounterexample` 667,334 (66.7%); edge count 582,459 (58.2%); edge hash 613,810 (61.4%). Escrow rows unchanged (`explore(CAP)` 940,335) | `evidence/budget.md` |
| Oracle | agrees with all 8 escrow and 7 vault pins, and with the generated edge table | `evidence/oracle.txt` |
| Bug zoo / conformance | 9 of 9 patches fail `fe build` naming their invariant and printing their digits; 13 of 13 conformance rows as expected (K7 and K8 added) | `evidence/check-bugs.txt`, `evidence/conformance.txt` |
| Tests | `fe test` 28 passed (Sonatina); `fe test --backend native` 10 passed | `evidence/transcript-tests.txt` |
| Differential | green at C = 21 | `evidence/differential.txt` |

Not changed, and why: `init` still accepts equal signer addresses, because `fe test` cannot change its caller and the vault
differential needs the one harness address as all three signers (README Limitations).
