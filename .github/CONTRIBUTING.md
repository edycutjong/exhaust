# Contributing to exhaust

Thanks for looking. exhaust is a small Fe project: a `const fn` explorer that the compiler runs under `static_assert`,
and the same `step()` function called from a deployed contract. Contributions that keep that claim honest are the
most useful ones.

## Getting started

1. Install the pinned compiler: Fe **v26.6.0** (`fe --version` must print `fe 26.6.0 (5b3f96a)`); the install line is in
   the README.
2. Fork the repo and branch from `main`: `git checkout -b fix/your-change`.
3. Run the whole check locally before you open a PR:

   ```sh
   sh tools/ci_local.sh          # fmt, check, build, tests on both backends, demo, bug zoo, conformance, oracle, bench smoke
   ```

## Before you open a pull request

- `fe fmt --check` is clean and `sh tools/ci_local.sh` ends with `RESULT: all steps passed`.
- A change to a model (`src/escrow*.fe`, `src/vault*.fe`) also updates `MODEL.md` and the pins, and the Python oracle
  (`tools/ref_model.py`, written independently of the Fe code) must still agree: `python3 tools/ref_model.py --check`.
- A new invariant needs a bug patch in `demo/` that fails `fe build` naming it, registered in `demo/bugs.tsv`.
- Numbers in the README come from `evidence/`; do not edit one without re-running the command in `DEMO.md`.
- Do not claim "verified" or "proved": the explorer is bounded-exhaustive at the stated capacities (see the README's
  limitations).

## Commit messages and releases

Commits follow the Angular convention; `release.yml` reads them to compute the next version, so the prefix matters:

| Prefix | Release |
|---|---|
| `fix:`, `perf:` | patch (`0.1.0` to `0.1.1`) |
| `feat:` | minor (`0.1.0` to `0.2.0`) |
| `feat!:` or a `BREAKING CHANGE:` footer | major |
| `docs:`, `chore:`, `test:`, `refactor:`, `style:`, `ci:` | none |

## Reporting bugs and requesting features

Use the issue templates. For a Fe compiler problem, include the smallest `.fe` file that reproduces it and the output of
`fe --version`. Security issues go through [SECURITY.md](SECURITY.md), not a public issue.

By contributing you agree that your contribution is licensed under the Apache License 2.0, like the rest of the repo.
