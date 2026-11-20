# Step budget per compile-time search (measured by bench/budget_probe.py)

2026-11-20 20:50 UTC · `fe 26.6.0 (5b3f96a)` · `Darwin Edy-MBP-M1-Max.local 27.2.0 Darwin Kernel Version 27.2.0: Thu Oct 15 00:02:46 PDT 2026; root:xnu-13432.41.4~25/RELEASE_ARM64_T6000 arm64 arm`

Fe 26.6.0 gives each `static_assert` evaluation a budget of **1,000,000 steps** and a recursion limit of **64**, with
no CLI or config override (`crates/hir/src/analysis/semantic/ctfe/machine.rs` lines 66-73 at tag v26.6.0). Consts that
reference other consts share one budget (`evidence/probes-2026-11-15.txt`, section 4), so every search below is its own
`static_assert`. Steps are measured indirectly: a burn loop fits 43,476 iterations alone (≈ 23.001 steps per iteration); each row is the
burn headroom lost when the search runs in the same assert, converted to steps (± a few steps).

| Search | States | Steps used | Share of 1M | Steps per state (after setup) | Note |
|---|---:|---:|---:|---:|---|
| `explore(0)` | 1 | 86,323 | 8.6% | — | 1 state, no successors: two 42,592-element tables initialised |
| `explore(17)` | 494 | 658,271 | 65.8% | 1,158 | spike capacity |
| `explore(CAP)` | 736 | 940,335 | 94.0% | 1,160 | the headline assert |
| `counterexample(19)` | 609 | 908,455 | 90.8% | 1,350 | green: full search; it sets up 4 tables, not 2, so its per-state column is overstated by ≈ 86k / 609 |
| `counterexample(20)` | 671 | 983,899 | 98.4% | 1,338 | fits, but too close to the limit for edits to step() (K2 exceeds it); not pinned |
| `fingerprint(CAP, false)` | 736 | 763,387 | 76.3% | 920 | no invariant checks |
| `fingerprint(CAP, true)` | 736 | 802,052 | 80.2% | 972 | u128 arithmetic |
| `explore_seeds(LOCKED_BASE + LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 91 | 190,749 | 19.1% | 1,148 |  |
| `explore_seeds(LOCKED_BASE + 8 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 238 | 362,821 | 36.3% | 1,162 |  |
| `explore_seeds(LOCKED_BASE + 15 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 385 | 534,870 | 53.5% | 1,165 |  |

Over the limit (measured with `fe build` on the same code, see `evidence/capacities.md`): `counterexample(21)`;
capacities above 21 do not fit the encoding (`MAX_CAP = 21`).
