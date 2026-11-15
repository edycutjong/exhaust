# Declaration: pre-existing work, reused code, AI assistance

Required by the Fe Builders Challenge 2026 rules. This file is updated as the project changes (last update: 2026-11-15).

## Pre-existing work

- **None before the build window opened (2026-11-03).**
- **Day-0 feasibility spike, 2026-11-15**, by the same author, in a private scratch folder outside this repository: a
  single-file escrow model explored by a `const fn` under `static_assert`, plus small probes of the compile-time step budget.
  It ran inside the build window on Fe 26.6.0. Its code was **ported into this ingot module by module, in separate commits**
  (model + `step()` → explorer + state pin → named invariants → counterexample → contract → tests), all landing in one
  sitting on 2026-11-15. The port restructured it (one `step()` taking the capacity as an argument, one shared invariant
  function, a transition form of `conserved`) rather than copying the files. Its measurements are treated as a baseline only; every number this repository states is re-measured here and
  recorded under `evidence/`.

## Reused code and third-party material

- **Fe standard library and core** (`std`, `core`) shipped with Fe 26.6.0: used, not modified. No other dependency.
- **The Fe Builders Challenge starter repository** (`fe-lang/builders-challenge-starter`, Apache-2.0): the CI workflow
  pattern (install Fe with `feup`, then `fe fmt --check` / `fe test` / `fe build`) and the license choice.
- **LICENSE**: the unmodified Apache License 2.0 text.
- Fonts or other assets added later for the project page are listed here when they are added.

## AI assistance

- **Claude Code** (Anthropic; Claude Opus 5.5 and Claude Sonnet 5.5) wrote most of the code and documentation under the
  author's direction: design, Fe source, tests, scripts and prose.
- **Outside models reviewed the specification** before any code was written: OpenAI Codex, xAI Grok and Alibaba Qwen
  (two review rounds). Their accepted suggestions changed the design (for example the transition form of the `conserved`
  invariant); they did not write repository code.
- The author is responsible for every line and can explain it. **The tests and the compile-time checks are the check**:
  `fe build` runs the search, exhaustive at the capacities stated in `evidence/capacities.md`, and `fe test` runs it again
  at runtime on two backends.
