## Summary

<!-- What does this change, and why? -->

## Changes

-

## Checklist

- [ ] `fe fmt --check` is clean and `sh tools/ci_local.sh` ends with `RESULT: all steps passed`
- [ ] A model change also updates `MODEL.md`, the pins, and `python3 tools/ref_model.py --check` still agrees
- [ ] A new invariant ships with a bug patch in `demo/` that fails `fe build` naming it
- [ ] README / DEMO numbers still come from `evidence/` (re-ran the command in `DEMO.md` if one changed)
- [ ] Commit messages follow the Angular prefixes (`fix:`, `feat:`, `docs:`, ...)

## Related issues

Closes #
