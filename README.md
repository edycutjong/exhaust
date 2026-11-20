# exhaust

**The Fe compiler is the model checker.** A `const fn` explores every reachable state of a small protocol state machine
inside `fe build`, at a stated capacity: the escrow at C = 21 units, all 736 reachable states and every accepted transition
checked against five named invariants. When an invariant breaks, `static_assert` fails the build: the compiler error names
the invariant, and a second diagnostic prints a shortest counterexample as action digits (searched at C′ = 19, two units below
the main check: C′ = 20 fits at 98.4% of the budget but leaves no room to edit `step()`, see `evidence/capacities.md`). The transition function that was checked, `step()`, is the same one the contract's `recv` handlers call, and
an exhaustive-edge differential test replays every reachable transition attempt through the deployed contract.

This is bounded-exhaustive checking at the stated capacities (the small-scope hypothesis), not formal verification.

**The ceiling.** Fe 26.6.0 gives each `static_assert` evaluation 1,000,000 evaluator steps and a recursion limit of 64, with
no CLI or config override. The C = 21 search uses 940,335 of them (≈ 86k to set up its two tables, then ≈ 1,160 steps per state); consts that reference other
consts share one budget, so a bigger model is split into independent asserts, never chained (`evidence/budget.md`).

> Fe Builders Challenge 2026. The core and its evidence are in place; this README is a stub that a fuller write-up replaces.

## Try it (macOS Apple Silicon or Linux x86-64; git, curl and patch; python3 not needed for this)

<!-- The Linux run (evidence/repro-linux-2026-11-21.txt) predates the vault, the native trace and the V3 patch. -->

1. `git clone https://github.com/edycutjong/exhaust && cd exhaust`
2. `curl -fsSL https://raw.githubusercontent.com/argotorg/fe/v26.6.0/feup/feup.sh | bash -s -- --version v26.6.0 --no-modify-path`
   then `export PATH=$HOME/.fe/bin:$PATH` and `fe --version` → `fe 26.6.0 (5b3f96a)`
3. `fe build && sh demo/run.sh`

`demo/run.sh` works on temp copies: it builds the escrow (green), applies a one-line bug to the Refund guard, builds again
(red: `invariant 'paid once' broken`, `left: 11234` = Deposit, Deposit, Lock, Release, Refund), replays that attack on the
patched contract (it pays twice) and on the real one (the Refund is refused).

## Build and test

```sh
fe build                              # the compile-time search (exhaustive at the stated capacities)
fe test                               # Sonatina (EVM) backend
fe test --backend native              # native backend (on Linux this needs a C linker, `cc`: apt-get install gcc libc6-dev)
sh tools/differential.sh              # the exhaustive-edge differential report (also part of fe test)
sh demo/check-bugs.sh                 # every bug patch must fail fe build naming its invariant and printing its digits
sh demo/check-bugs.sh --conformance   # the checker's own negative tests
python3 tools/ref_model.py --check    # the Python oracle (follows MODEL.md) against every pin
sh tools/trace.sh demo/vault-execute-early.patch   # native trace of a bug by action name (macOS arm64; see tools/trace.sh)
python3 tools/decode-trace 1236 --protocol vault --bug vault-execute-early   # digits from the compile error -> names
```

## Limitations: what this does not prove

- Only the stated capacities are explored (C = 21 for the state count, C′ = 19 for the printed trace); behaviour above them is
  not checked. Liveness is not checked, only safety invariants.
- The escrow model has no caller identity: `msg.sender` authorization is not modelled. Units are abstract counters: no ETH or
  token moves, so value transfer, reentrancy and gas are out of scope.
- The contract is a model-faithful demonstrator, not a custody contract: there is no access control (any address can call
  any handler), and a rejected transition returns `false` instead of reverting.
- The differential test covers every transition reachable through the handlers at C = 21; storage states the handlers cannot
  reach (an upgrade, a storage collision) are not covered.
- `MODEL.md`, the Fe model and the oracle share one author and one reading of the protocol. The oracle is independent in
  language and state representation (Python tuples; its edge table packs states differently), but its edge hash uses the
  same radix-22 index formula as the Fe encoding. A misreading shared by all three is not caught.
- The vault (second protocol, `MODEL.md`) is explored at B = 10 with T = 3, plus T = 1, T = 2 and a B = 8, T = 2 baseline as separate
  models. Its contract has no `Tick` handler and the `fe test` harness can neither move the block time nor change the caller, so the
  contract's own graph has 91 states (lock period passed) and 9 (a lock that never passes) against the model's 211, and the vault
  differential replays exactly those; all three signers are one address in the tests. Caller authorization, the exact lock boundary (`queued_at`) and signer distinctness are untested, and `init` does not
  require the three signer addresses to differ.
- `in bounds` cannot fire first for this escrow (`within capacity` implies it); it guards the encoding for future edits.

Action legend: 1 Deposit · 2 Lock · 3 Release · 4 Refund · 5 Dispute. The model in words: `MODEL.md`. Numbers: `evidence/`.

License: Apache-2.0. See `DECLARATION.md` for pre-existing work, reused code and AI assistance.
