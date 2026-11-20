# Named capacities (Fe 26.6.0)

One row per pin. A capacity is the escrow's unit limit `cap`; the encoding holds any `cap <= 21` (radix 22, `MAX_CAP`).
Each search is exhaustive only at the capacity named in its row. Step counts: `budget.md` (bench/budget_probe.py).

| Name | Capacity | What runs there | Limit measured |
|---|---|---|---|
| C_model | 21 | `static_assert(explore(CAP) == 736)` in `src/escrow_explore.fe`, every invariant on every reachable state and accepted edge; also the contract's `CAP` | 940,335 of 1,000,000 steps (`budget.md`); 21 is also `MAX_CAP`, the largest capacity the encoding holds |
| C′ (trace) | 20 | `static_assert(counterexample(20) == 0)` | 983,899 steps; `counterexample(21)` exceeds the step limit (`fe build`, 2026-11-21) |
| C_diff | 21 | `test_differential_all_edges` (EVM): every reachable transition attempt replayed through the deployed contract | one test, no shard needed (`differential.txt`) |
| shards | 21 | three `explore_seeds` asserts over the locked amount k = 1..7, 8..14, 15..21: 91 + 238 + 385 states, + 22 Open states = 736 | disjoint by construction (after Lock the total is fixed); sum checked by `test_shards_partition` on both backends, disjointness and union by `tools/ref_model.py` |
| spike | 17 | `static_assert(explore(17) == 494)`, the day-0 spike's capacity | a regression pin on the encoding, not extra coverage: the escrow's reachable sets nest (only Deposit reads `cap`) |
| C_hash, C_table | — | labeled-edge hash pin and oracle edge table (`test_oracle_edges`): not shipped yet | P1a probe: both fit at 21 (`probes-2026-11-15.txt`) |

History: P1a (2026-11-15) had C_model = 19 (609) and C′ = 18; P1b leaned `step()` and the predicate (no helper calls on the
hot path), which moved them to 21 and 20.
