# exhaust

**The Fe compiler is the model checker.** A `const fn` explores every reachable state of a small protocol state machine
inside `fe build`, at a stated capacity: the escrow at C = 21 units, all 736 reachable states and every accepted transition
checked against five named invariants. When an invariant breaks, `static_assert` fails the build: the compiler error names
the invariant, and a second diagnostic prints a shortest counterexample as action digits (searched at C′ = 20, one unit below
the main check). The transition function that was checked, `step()`, is the same one the contract's `recv` handlers call, and
an exhaustive-edge differential test replays every reachable transition attempt through the deployed contract.

This is bounded-exhaustive checking at the stated capacities (the small-scope hypothesis), not formal verification.

> Work in progress (Fe Builders Challenge 2026). The full README, evidence and limitations land before submission.

## Try it (Linux x86-64 or macOS Apple Silicon; git + curl; python3 not needed for this)

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
fe test --backend native              # native backend (on Linux this needs a C linker, `cc`)
sh demo/check-bugs.sh                 # every bug patch must fail fe build naming its invariant and printing its digits
sh demo/check-bugs.sh --conformance   # the checker's own negative tests
python3 tools/ref_model.py --check    # the independent oracle (written from MODEL.md) against every pin
```

Action legend: 1 Deposit · 2 Lock · 3 Release · 4 Refund · 5 Dispute. The model in words: `MODEL.md`. Numbers: `evidence/`.

License: Apache-2.0. See `DECLARATION.md` for pre-existing work, reused code and AI assistance.
