# Step budget per compile-time search (measured by bench/budget_probe.py)

2026-11-20 22:41 UTC · `fe 26.6.0 (5b3f96a)` · `Darwin Edy-MBP-M1-Max.local 27.2.0 Darwin Kernel Version 27.2.0: Thu Oct 15 00:02:46 PDT 2026; root:xnu-13432.41.4~25/RELEASE_ARM64_T6000 arm64 arm`

Fe 26.6.0 gives each `static_assert` evaluation a budget of **1,000,000 steps** and a recursion limit of **64**, with
no CLI or config override (`crates/hir/src/analysis/semantic/ctfe/machine.rs` lines 66-73 at tag v26.6.0). Consts that
reference other consts share one budget (`evidence/probes-2026-11-15.txt`, section 4), so every search below is its own
`static_assert`. Steps are measured indirectly: a burn loop fits 43,476 iterations alone (≈ 23.001 steps per iteration); each row is the
burn headroom lost when the search runs in the same assert, converted to steps (resolution: one burn iteration, ≈ 23 steps).

| Search | States | Steps used | Share of 1M | Steps per state (after setup) | Note |
|---|---:|---:|---:|---:|---|
| `explore(0)` | 1 | 86,323 | 8.6% | — | 1 state, no successors: two 42,592-element tables initialised |
| `explore(17)` | 494 | 658,271 | 65.8% | 1,158 | spike capacity |
| `explore(CAP)` | 736 | 940,335 | 94.0% | 1,160 | the headline assert |
| `counterexample(19)` | 609 | 908,455 | 90.8% | 1,350 | green: full search; it sets up 4 tables, not 2, so its per-state column is overstated by ≈ 86k / 609 |
| `counterexample(20)` | 671 | 983,899 | 98.4% | 1,338 | fits, but too close to the limit for edits to step() (K2 exceeds it); not pinned |
| `fingerprint(CAP, false, STATES)` | 736 | 775,899 | 77.6% | 937 | no invariant checks |
| `fingerprint(CAP, true, STATES)` | 736 | 815,507 | 81.5% | 991 | u128 arithmetic |
| `explore_seeds(LOCKED_BASE + LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 91 | 190,749 | 19.1% | 1,148 |  |
| `explore_seeds(LOCKED_BASE + 8 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 238 | 362,821 | 36.3% | 1,162 |  |
| `explore_seeds(LOCKED_BASE + 15 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)` | 385 | 534,870 | 53.5% | 1,165 |  |
| `vexplore(0, 0)` | 1 | 94,581 | 9.5% | — | B = 0: no unit to propose, one state; two 46,464-element tables initialised |
| `vexplore(8, 2)` | 137 | 414,160 | 41.4% | 2,333 | the baseline configuration (B = 8, T = 2) |
| `vexplore(VB, VT)` | 211 | 586,761 | 58.7% | 2,333 | the vault's headline assert |
| `vcounterexample(VB, VT)` | 211 | 667,380 | 66.7% | 2,715 | green: full search; four tables, so its per-state column is overstated |
| `vsearch(VB, VT, V_COUNT_EDGES)` | 211 | 582,482 | 58.2% | 2,312 | the vault's edge-count pin: the same checked search, counting edges |
| `vsearch(VB, VT, V_HASH_EDGES)` | 211 | 613,833 | 61.4% | 2,461 | the vault's edge-hash pin: the same checked search, u128 hash |
| `vexplore(10, 1)` | 131 | 401,325 | 40.1% | 2,342 | separate model (T = 1), not a part of the headline |
| `vexplore(10, 2)` | 171 | 494,043 | 49.4% | 2,336 | separate model (T = 2), not a part of the headline |

Over the limit (measured with `fe build` on the same code, see `evidence/capacities.md`): `counterexample(21)`;
capacities above 21 do not fit the encoding (`MAX_CAP = 21`).
