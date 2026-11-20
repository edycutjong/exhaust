# Porting the pattern to a second protocol: the vault (spec.md D8)

How much work was it to take the escrow's pattern (a pure `step()`, one explorer, named invariants, a contract that calls
`step()`, a differential test, a bug patch that fails the build) and point it at a different state machine? Recorded during the
vault port, 2026-11-21, `fe 26.6.0 (5b3f96a)`. No outreach, no second author: the port was done by the same author as the escrow
(with an AI coding assistant, see `DECLARATION.md`), so this is evidence about the pattern's mechanics, not a usability study.

## Size of the port

| File | Lines | Escrow counterpart (lines) | What it is |
|---|---:|---|---|
| `src/vault.fe` | 394 | `src/escrow.fe` (286) | state, actions, encoding, `vstep()`, seven invariants |
| `src/vault_explore.fe` | 173 | `src/escrow_explore.fe` (269) | `vexplore()`, `vcounterexample()`, five pins (no edge hash, no shards) |
| `src/vault_contract.fe` | 156 | `src/escrow_contract.fe` (87) | `recv` handlers over `vstep()`; adds the caller → signer and block time → clock adapter |
| `src/vault_tests.fe` | 472 | `src/tests.fe` (447) | runtime agreement, scripted run, per-handler suite, differential |
| `demo/vault-*.patch` | 12 each | `demo/*.patch` | one guard removed each (V1, V2) |

`fe fmt` expands struct literals one field per line (about a fifth of `vault.fe`'s lines). The explorer is a copy with every
identifier `v`-prefixed (`explore` → `vexplore`, `step` → `vstep`, `INIT` → `vinit_index(b)`, `require` → `vrequire`, …) and a `(b, t)`
signature instead of `cap`; it is not generic, by design (a monomorphic explorer per protocol).

## Time

The vault model, explorer, contract, tests and the first two bug patches were committed in five commits (`git log`, 2026-11-21
04:2x, between the autopilot's `P1c START` 04:16 and its first checkpoint 04:25 on that clock), interleaved with the oracle and bench
work, so read it as an upper bound of minutes, not hours. Both red patches failed `fe build` naming their invariant and printing their
digits when first run (`evidence/check-bugs.txt`).

## Failure points hit

Things that did not work the first time, in the order they came up:

1. **Table size.** The first configuration, B = 16 and T = 3 (box 110,976), fit one `static_assert` (95.1% of the budget) but the
   attack printer `vcounterexample` did not (four tables). The box was cut to B ≤ 10, T ≤ 3 (46,464): the headline assert now uses 55.2% of the budget and the attack printer 65.4% (`evidence/budget.md`). This is the pattern's one real cost: **the model size is set by the 1,000,000-step budget, and every extra field multiplies the box.**
2. **`Duration::from_secs` does not exist** in 26.6.0; the starter repo's tests use `std::evm::days(n)` and `Duration::zero()`.
3. **`usize` → `u32` with `as` is rejected**; `.downcast_truncate()` is the lossless-looking spelling used elsewhere.
4. **`Timestamp` is not a `u256`**: no `.seconds`, no cast. Block time stays a `Timestamp`, compared as `now >= queued_at + lock`.
5. **`evm.caller()` in a test is not the address contracts see as `msg.sender`.** A helper contract that returns `ctx.caller()` is
   deployed first, and its answer is used as all three signers. So the three-signer check cannot be tested with distinct callers.
6. No semicolons, labelled arguments need `_` (`fn f(_ x: ...)`), and a `mut` array argument also needs the `_`.

The compiler messages for 2–4 and the harness limit in 5 are in `FE-NOTES.md`.

## What the port did not need to change

The encoding scheme, the BFS, the `static_assert` pin pattern, the digit counterexample, the shared `step()` in `recv` handlers,
the per-action `bugs.tsv` row, the oracle structure and the `black_box` runtime agreement all carried over unchanged. The
conformance-style mutation check also carried over: three one-line mutations of `vault_contract.fe` (store the wrong field, ignore the
lock period, skip the signer check) were run; the first two make `test_vault_differential` fail, the third (skip the signer-B check) is **not caught**,
because the harness cannot send from a different address. That row is in the README's "What this does not prove".

## Ablation: what the contract tests alone catch

`demo/check-bugs.sh` runs the patched vault through the contract tests with the pins removed. With the vault's handler suite
(`test_vault_handler_*`) and the scripted run (`test_vault_contract_matches_vstep`): V1 `vault-approve-twice` is caught by the handler
suite (1 of 4) and missed by the scripted run; V2 `vault-execute-early` is missed by both; V3 `vault-pay-twice` is caught by both
(1 of 4 handler tests, and the scripted run). `test_vault_timelock_holds` (a separate test,
not in either filter) does fail on V2, and so do `test_vault_differential` and the runtime agreement tests (run by hand on the stripped patched copy; not in `check-bugs.sh`):
a test written knowing the bug catches it; the search finds it without being told.
