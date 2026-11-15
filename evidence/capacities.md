# Named capacities (Fe 26.6.0, measured 2026-11-15)

One row per pin in `src/escrow_explore.fe`. A capacity is the escrow's unit limit `cap`; the encoding holds any `cap <= 21`
(radix 22). The search is exhaustive only at the capacity named in its row.

| Name | Capacity | What runs there | Limit measured |
|---|---|---|---|
| C_model | 19 | `static_assert(explore(CAP) == 609)`, every invariant checked; also the contract's `CAP` | C = 20 exceeds the 1,000,000-step limit |
| C′ (trace) | 18 | `static_assert(counterexample(18) == 0)` | C = 19 exceeds the limit |
| spike | 17 | `static_assert(explore(17) == 494)`, the day-0 spike's capacity | a regression pin on the encoding, not extra coverage: the escrow's reachable sets nest (only Deposit reads `cap`) |

Source: `probes-2026-11-15.txt` (section 5) and `p1a-port-2026-11-15.md`.
