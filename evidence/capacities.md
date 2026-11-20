# Named capacities (Fe 26.6.0)

One row per pin. A capacity is the escrow's unit limit `cap`; the encoding holds any `cap <= 21` (radix 22, `MAX_CAP`).
Each search is exhaustive only at the capacity named in its row. Step counts: `budget.md` (bench/budget_probe.py).

| Name | Capacity | What runs there | Limit measured |
|---|---|---|---|
| C_model | 21 | `static_assert(explore(CAP) == STATES)`, STATES = 736, in `src/escrow_explore.fe`, every invariant on every reachable state and accepted edge; also the contract's `CAP` | 940,335 of 1,000,000 steps (`budget.md`); 21 is also `MAX_CAP`, the largest capacity the encoding holds |
| C′ (trace) | 19 | `static_assert(counterexample(19) == 0)` | 908,455 steps. `counterexample(20)` fits at 983,899 steps but conformance K2 (two extra branches in `step()`) pushes it over, so it is not pinned; `counterexample(21)` exceeds the limit (`fe build`, 2026-11-21) |
| C_diff | 21 | `test_differential_all_edges` (EVM): every reachable transition attempt replayed through the deployed contract | one test, no shard needed (`differential.txt`) |
| shards | 21 | three `explore_seeds` asserts over the locked amount k = 1..7, 8..14, 15..21: 91 + 238 + 385 states, + 22 Open states = 736 | disjoint by construction (after Lock the total is fixed); sum checked by `test_shards_partition` on both backends, disjointness and union by `tools/ref_model.py` |
| spike | 17 | `static_assert(explore(17) == 494)`, the day-0 spike's capacity | a regression pin on the encoding, not extra coverage: the escrow's reachable sets nest (only Deposit reads `cap`) |
| C_hash | 21 | `fingerprint(CAP, false, STATES)` == EDGES = 966 (accepted edges) and `fingerprint(CAP, true, STATES)` == EDGE_HASH = 1194004490208706542 (labeled-edge hash, MODEL.md); both stop past STATES states and defer to `explore` | 775,899 and 815,507 steps |
| C_table | 21 | `test_oracle_edges` (both backends): `step()` against all 3,680 attempts of the generated `src/oracle_edges.fe` | about 1 s per backend for `fe test --filter test_oracle_edges` (wall, incl. compile) |

History: P1a (2026-11-15) had C_model = 19 (609) and C′ = 18; P1b leaned `step()` and the predicate (no helper calls on the
hot path), which moved them to 21 and 20; C′ was then set to 19 for headroom (see the C′ row).
