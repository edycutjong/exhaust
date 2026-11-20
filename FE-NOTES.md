# Fe notes (friction log, Fe 26.6.0)

- `fe build` on an ingot without a contract prints `Error: No contracts found to build` and exits 1 even when every
  `static_assert` held. `fe check` evaluates `static_assert` too, and exits 0.
- Array initialisation in const evaluation costs about one evaluator step per element, so table sizes count against the
  1,000,000-step budget (`evidence/p1a-port-2026-11-15.md`, probe 3).
- `fe test --backend native` on Linux needs a host C linker (`cc`); without one the native suite fails with
  `host linker \`cc\` failed`.
- The test `Evm` has no way to set the block timestamp or the caller of `evm.call`: `impl Ctx for Evm`
  (`ingots/std/src/evm/effects.fe:885` at v26.6.0) only reads them.
- Every function call costs evaluator steps in const evaluation. Writing `step()` and the invariant predicate without helper
  calls (inline field arithmetic, `match` on the phase) cut the explorer to ≈ 1,160 steps per state and moved the largest
  capacity that fits one assert from 19 to 21 (`evidence/budget.md`, `evidence/p1b-core-2026-11-21.md`).
- There is no step counter to read; `bench/budget_probe.py` measures a search's cost indirectly, by bisecting a burn loop in
  the same `static_assert` (a bare `while i < n { i += 1 }` iteration costs ≈ 23 steps).
- A failed `static_assert` stops `fe test` from running at all, so tests of a deliberately broken model run in a
  "gate-stripped" temp copy with the pins removed (`demo/run.sh`, `demo/check-bugs.sh`).
- Vault port (P1c), compiler messages as printed by `fe 26.6.0 (5b3f96a)`:
  - `error[2-0010]: no method named \`from_secs\` found for struct \`Duration\``: use `std::evm::days(n)` and `Duration::zero()`.
  - `error[8-0055]: cast is not provably lossless` for `usize as u32`: use `.downcast_truncate()`.
  - `error[8-0015]: invalid field index ... field \`seconds\` is not found in \`Timestamp\``, and `expected \`u256\`, but \`Timestamp\` is given`:
    block time stays a `Timestamp` (compare `now >= queued_at + lock`).
  - In a test, `evm.caller()` is not the address a called contract sees as `msg.sender`: a helper contract returning
    `ctx.caller()` is deployed and called first (`src/vault_tests.fe`, contract `Who`). using `#[cfg(test)]` on `Who` made the test build fail, so it is
    `#[cfg(target = "evm")]` and also appears in `fe build` output as `Who.bin`.
  - `fe test --backend native` rejects `--show-logs` (`native tests do not support EVM logs or tracing options`).
