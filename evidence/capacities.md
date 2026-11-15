# Named capacities (Fe 26.6.0, measured 2026-11-15)

One row per pin. A capacity is the escrow's unit limit `cap`; the encoding holds any `cap <= 21` (radix 22).

| Name | Capacity | What runs there | Status |
|---|---|---|---|
| C_model | 19 | `static_assert(explore(CAP) == 609)`, every invariant checked; the contract's `CAP` | pinned; C = 20 exceeds the 1,000,000-step limit |
| C′ (trace) | 18 | `static_assert(counterexample(18) == 0)` | pinned; C = 19 exceeds the limit |
| spike | 17 | `static_assert(explore(17) == 494)`, the day-0 spike's capacity | pinned (regression on the encoding, not extra coverage: the escrow's reachable sets nest) |
| C_hash | 21 (probe) | labeled-edge hash, no invariant checks | fits (p1a-port probe 9); not yet pinned |
| C_table | 21 (probe) | generated oracle edge table, 3,680 rows | compiles and runs (probe 8); not yet in the repo |
| C_diff | 19 (planned) | exhaustive-edge differential against the contract | not yet built |

Source: `p1a-port-2026-11-15.md` (probes 7–9).
