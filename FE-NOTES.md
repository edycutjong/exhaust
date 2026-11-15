# Fe notes (friction log, Fe 26.6.0)

- `fe build` on an ingot without a contract prints `Error: No contracts found to build` and exits 1 even when every
  `static_assert` held. `fe check` evaluates `static_assert` too, and exits 0.
- Array initialisation in const evaluation costs about one evaluator step per element, so table sizes count against the
  1,000,000-step budget (`evidence/p1a-port-2026-11-15.md`, probe 3).
- `fe test --backend native` on Linux needs a host C linker (`cc`); without one the native suite fails with
  `host linker \`cc\` failed`.
- The test `Evm` has no way to set the block timestamp or the caller of `evm.call`.
