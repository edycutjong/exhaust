# DEMO: reproduce every number

Every figure in `README.md` comes from a command below, run on `fe 26.6.0 (5b3f96a)` (macOS Apple Silicon; the Linux x86-64
container run is `evidence/repro-linux-2026-11-21.txt`). The raw output is committed in `evidence/`; most files record the
commit, the Fe version and the machine in their header. Install Fe first (pinned):

```sh
curl -fsSL https://raw.githubusercontent.com/argotorg/fe/v26.6.0/feup/feup.sh | bash -s -- --version v26.6.0 --no-modify-path
export PATH=$HOME/.fe/bin:$PATH
fe --version        # fe 26.6.0 (5b3f96a)
```

## The 60-second demo

```sh
fe build            # green: explore(CAP) == STATES held, 736 states at C = 21, every invariant on every state and edge
sh demo/run.sh      # red: invariant 'paid once' broken, left: `11234`; then the attack replayed on the patched and the real contract
```

Output: `evidence/demo-run.txt` (green run: `evidence/transcript-pass.txt`; the failing build: `evidence/transcript-fail-refund-after-release.txt`).

## Number to command

| Claim in the README | Command | Where the output is |
|---|---|---|
| 736 states, 966 edges, 3,680 attempts, depth 43 at C = 21 | `sh bench/run.sh` (section 1), pinned by `static_assert(explore(CAP) == STATES)` in `fe build` | `evidence/bench-2026-11-20.md` §1 |
| 940,335 of 1,000,000 steps; 86,323 setup; about 1,160 per state | `sh bench/run.sh` (section 2, `bench/budget_probe.py` loop bisection) | `evidence/budget.md`, `evidence/budget.json` |
| Attack printer C′ = 19 (908,455 steps); C′ = 20 fits at 98.4% | `sh bench/run.sh` | `evidence/capacities.md`, `evidence/bench-2026-11-20.md` §2 |
| Shards 91 + 238 + 385 + 22 Open, disjoint, union = 736 | `python3 tools/ref_model.py --check` | `evidence/oracle.txt` |
| Python oracle agrees with all 15 Fe pins (8 escrow, 7 vault) and the 3,680-row edge table | `python3 tools/ref_model.py --check` | `evidence/oracle.txt`, `evidence/oracle.json` |
| Vault B = 10, T = 3: 211 states, 580 edges, 586,715 steps | `sh bench/run.sh` (section 5) | `evidence/bench-2026-11-20.md` §5 |
| 28 tests on Sonatina, 10 on native | `fe test`; `fe test --backend native` | `evidence/transcript-tests.txt` |
| Differential: 1,008 deployments, 25,646 calls, 736 states, 966 edges | `sh tools/differential.sh` | `evidence/differential.txt` |
| 16,394,182 gas for the runtime search (C = 17, 494 states) | `fe test --filter test_runtime_search_gas --show-logs` | `evidence/gas.txt` |
| 9 of 9 bug patches fail `fe build` naming the invariant and printing the digits | `sh demo/check-bugs.sh` | `evidence/check-bugs.txt`, one transcript per patch: `evidence/transcript-fail-<patch>.txt` |
| The checker's own negative tests | `sh demo/check-bugs.sh --conformance` | `evidence/conformance.txt` |
| Native trace by action name | `sh tools/trace.sh demo/refund-after-release.patch` (macOS arm64) | `evidence/transcript-trace-<patch>.txt` |
| Digits to action names | `python3 tools/decode-trace 11234 --bug refund-after-release` (vault: `--protocol vault --bug vault-execute-early`) | stdout |
| CI steps, locally | `sh tools/ci_local.sh` | `evidence/ci-local-2026-11-21.txt` |
| Fresh clone reproduces | `sh tools/repro_linux.sh` | `evidence/repro-linux-2026-11-21.txt` (clean clone at 7b5e404, 28 + 10 tests; `evidence/repro-clone-2026-11-21.txt` is an earlier run that predates the vault) |

## Decoding the digits

Escrow: 1 Deposit · 2 Lock · 3 Release · 4 Refund · 5 Dispute. Vault: 1 Propose · 2 ApproveA · 3 ApproveB · 4 ApproveC ·
5 Tick · 6 Execute · 7 Cancel. `11234` is Deposit, Deposit, Lock, Release, Refund: on the patched model the seller and the buyer are both paid; on the real model the Refund is refused.

## What this does not show

Bounded-exhaustive checking at the stated capacities, not formal verification; no liveness; the "Limitations" section of
`README.md` lists the rest. Wall times in the benchmark file carry little signal (the step budget decides what fits).
