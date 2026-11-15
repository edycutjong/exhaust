# exhaust

**The Fe compiler is the model checker.** A `const fn` explores every reachable state of a small protocol state machine
inside `fe build`, at a stated capacity (the escrow at C = 19 units: all 609 reachable states and every accepted
transition checked against five named invariants); `static_assert` fails the build when an invariant breaks: the compiler error names
the invariant, and a second diagnostic prints a shortest counterexample as action digits (searched at C′ = 18, one unit
below the main check); and the transition function that was checked, `step()`, is the same one
the contract's `recv` handlers call.

> Work in progress (Fe Builders Challenge 2026). The full README, evidence and limitations land before submission.

## Build and test

Requires Fe 26.6.0 (`fe --version` → `fe 26.6.0 (5b3f96a)`).

```sh
fe build                     # runs the compile-time search (exhaustive at the stated capacities)
fe test                      # Sonatina (EVM) backend
fe test --backend native     # native backend (on Linux this needs a C linker, `cc`)
```

License: Apache-2.0. See `DECLARATION.md` for pre-existing work, reused code and AI assistance.
