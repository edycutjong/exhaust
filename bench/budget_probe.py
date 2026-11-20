#!/usr/bin/env python3
"""Step-budget table: how many of the 1,000,000 CTFE evaluator steps each compile-time search uses (Fe 26.6.0).

Method (no compiler instrumentation exists): Fe gives every static_assert evaluation one budget of 1,000,000 steps.
A burn loop `burn(n)` costs a fixed number of steps per iteration. In a gate-stripped temp copy of this ingot:
  1. calibrate: the largest N with static_assert(burn(N) == N) passing  ->  steps per iteration ~ 1,000,000 / N0
  2. per search S: the largest N with static_assert(S + burn(N) == pin + N) passing  ->  steps(S) ~ (N0 - N) * per-iteration
Bisection to 1 iteration. Writes evidence/budget.md and evidence/budget.json. Usage: python3 bench/budget_probe.py
"""
import json
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 1_000_000

# (label, Fe expression of type usize/u256, pin, states explored, note)
SEARCHES = [
    ("explore(0): array setup only", "explore(0)", 1, 1, "1 state, no successors: two 42,592-element tables initialised"),
    ("explore(17)", "explore(17)", 494, 494, "spike capacity"),
    ("explore(CAP), C_model = 21", "explore(CAP)", 736, 736, "the headline assert"),
    ("counterexample(19), C' = 19", "counterexample(19)", 0, 609,
     "green: full search; it sets up 4 tables, not 2, so its per-state column is overstated by ≈ 86k / 609"),
    ("counterexample(20)", "counterexample(20)", 0, 671, "fits, but too close to the limit for edits to step() (K2 exceeds it); not pinned"),
    ("edge count, C_hash = 21", "fingerprint(CAP, false, STATES)", 966, 736, "no invariant checks"),
    ("labeled-edge hash, C_hash = 21", "fingerprint(CAP, true, STATES)", 1194004490208706542, 736, "u128 arithmetic"),
    ("shard A, k = 1..7", "explore_seeds(LOCKED_BASE + LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)", 91, 91, ""),
    ("shard B, k = 8..14", "explore_seeds(LOCKED_BASE + 8 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)", 238, 238, ""),
    ("shard C, k = 15..21", "explore_seeds(LOCKED_BASE + 15 * LOCKED_STRIDE, 7, LOCKED_STRIDE, CAP)", 385, 385, ""),
    ("vexplore(0, 0): vault array setup only", "vexplore(0, 0)", 1, 1, "B = 0: no unit to propose, one state; two 46,464-element tables initialised"),
    ("vexplore(8, 2): baseline", "vexplore(8, 2)", 137, 137, "the baseline configuration (B = 8, T = 2)"),
    ("vexplore(VB, VT), B = 10, T = 3", "vexplore(VB, VT)", 211, 211, "the vault's headline assert"),
    ("vcounterexample(VB, VT)", "vcounterexample(VB, VT)", 0, 211, "green: full search; four tables, so its per-state column is overstated"),
    ("vsearch(VB, VT, V_COUNT_EDGES)", "vsearch(VB, VT, V_COUNT_EDGES)", 580, 211, "the vault's edge-count pin: the same checked search, counting edges"),
    ("vsearch(VB, VT, V_HASH_EDGES)", "vsearch(VB, VT, V_HASH_EDGES)", 1115689132712769016, 211, "the vault's edge-hash pin: the same checked search, u128 hash"),
    ("vexplore(10, 1)", "vexplore(10, 1)", 131, 131, "separate model (T = 1), not a part of the headline"),
    ("vexplore(10, 2)", "vexplore(10, 2)", 171, 171, "separate model (T = 2), not a part of the headline"),
]

HEADER = """use ingot::escrow::CAP
use ingot::escrow_explore::{explore, explore_seeds, counterexample, fingerprint, STATES, LOCKED_BASE, LOCKED_STRIDE}
use ingot::vault::{VB, VT}
use ingot::vault_explore::{vexplore, vcounterexample, vsearch, V_COUNT_EDGES, V_HASH_EDGES}

const fn burn(_ n: u32) -> u32 {
    var i: u32 = 0
    while i < n {
        i += 1
    }
    n
}
"""


def make_copy():
    d = Path(tempfile.mkdtemp(prefix="exhaust-budget-"))
    shutil.copy(ROOT / "fe.toml", d)
    shutil.copytree(ROOT / "src", d / "src")
    ex = d / "src" / "escrow_explore.fe"
    text = ex.read_text()
    ex.write_text(text[: text.index("// ---- pins")])  # gate-stripped: only the probe's assert runs
    vx = d / "src" / "vault_explore.fe"
    vtext = vx.read_text()
    vx.write_text(vtext[: vtext.index("// ---- pins")])
    return d


def fits(d, body):
    (d / "src" / "budget_probe.fe").write_text(HEADER + body + "\n")
    r = subprocess.run(["fe", "check"], cwd=d, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if "step limit" in out:
        return False
    if r.returncode != 0:
        raise SystemExit(f"probe did not compile:\n{body}\n{out[-2000:]}")
    return True


def largest(d, make, hi):
    lo = 0
    if not fits(d, make(0)):
        return None
    while lo < hi:  # invariant: fits(lo); not known about hi
        mid = (lo + hi + 1) // 2
        if fits(d, make(mid)):
            lo = mid
        else:
            hi = mid - 1
    return lo


def main():
    d = make_copy()
    t0 = time.time()
    n0 = largest(d, lambda n: f"static_assert(burn({n}) == {n})", LIMIT)
    per = LIMIT / n0
    rows = []
    for label, expr, pin, states, note in SEARCHES:
        cast = "as u256" if expr.startswith(("counterexample", "vcounterexample")) else "as u128" if expr.startswith(("fingerprint", "vsearch")) else "as usize"
        n = largest(d, lambda k: f"static_assert({expr} + (burn({k}) {cast}) == {pin} + {k})", n0)
        steps = None if n is None else round((n0 - n) * per)
        rows.append({"search": label, "expr": expr, "pin": pin, "states": states, "steps": steps,
                     "share_of_limit": None if steps is None else round(steps / LIMIT, 4), "note": note})
    setups = {"e": rows[0]["steps"], "v": next(r["steps"] for r in rows if r["expr"] == "vexplore(0, 0)")}
    for r in rows:
        setup = setups["v" if r["expr"].startswith(("vexplore", "vcounter", "vsearch")) else "e"]
        r["steps_per_state_after_setup"] = (None if r["steps"] is None or r["states"] <= 1
                                            else round((r["steps"] - setup) / r["states"]))
    fe = subprocess.run(["fe", "--version"], capture_output=True, text=True).stdout.strip()
    meta = {"fe": fe, "uname": " ".join(platform.uname()), "python": platform.python_version(),
            "limit": LIMIT, "burn_iterations_that_fit": n0, "steps_per_burn_iteration": round(per, 4),
            "probe_wall_time_s": round(time.time() - t0, 1), "date_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime())}
    (ROOT / "evidence" / "budget.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1) + "\n")
    lines = [
        "# Step budget per compile-time search (measured by bench/budget_probe.py)",
        "",
        f"{meta['date_utc']} UTC · `{fe}` · `{meta['uname']}`",
        "",
        "Fe 26.6.0 gives each `static_assert` evaluation a budget of **1,000,000 steps** and a recursion limit of **64**, with",
        "no CLI or config override (`crates/hir/src/analysis/semantic/ctfe/machine.rs` lines 66-73 at tag v26.6.0). Consts that",
        "reference other consts share one budget (`evidence/probes-2026-11-15.txt`, section 4), so every search below is its own",
        "`static_assert`. Steps are measured indirectly: a burn loop fits "
        f"{n0:,} iterations alone (≈ {per:.3f} steps per iteration); each row is the",
        "burn headroom lost when the search runs in the same assert, converted to steps (resolution: one burn iteration, ≈ 23 steps).",
        "",
        "| Search | States | Steps used | Share of 1M | Steps per state (after setup) | Note |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        s = "over limit" if r["steps"] is None else f"{r['steps']:,}"
        sh = "—" if r["share_of_limit"] is None else f"{100 * r['share_of_limit']:.1f}%"
        ps = "—" if r["steps_per_state_after_setup"] is None else f"{r['steps_per_state_after_setup']:,}"
        lines.append(f"| `{r['expr']}` | {r['states']:,} | {s} | {sh} | {ps} | {r['note']} |")
    lines += ["", "Over the limit (measured with `fe build` on the same code, see `evidence/capacities.md`): `counterexample(21)`;",
              "capacities above 21 do not fit the encoding (`MAX_CAP = 21`).", ""]
    (ROOT / "evidence" / "budget.md").write_text("\n".join(lines))
    print("\n".join(lines))
    shutil.rmtree(d)


if __name__ == "__main__":
    main()
