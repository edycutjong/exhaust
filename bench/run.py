#!/usr/bin/env python3
"""Deterministic benchmark driver. Usage: sh bench/run.sh [--skip-budget] [--date YYYY-MM-DD]

Writes evidence/bench-<date>.json and evidence/bench-<date>.md. Counts (states, edges, attempts) are exact and come from
the Python oracle (tools/ref_model.py); every `fe check` row is a pass/fail against that oracle count, so a row that says
`pass` means the Fe compile-time search agrees with the oracle at that size. Wall times are the median of 5 `fe check`
runs on this machine (they vary between machines and runs; the counts do not). Standard library only.

Sections: (1) escrow capacity sweep, (2) the step budget (bench/budget_probe.py), (3) shard scaling 1/2/4/8,
(4) runtime search gas on the EVM backend and time on the native backend, (5) the vault.
"""
import json
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ref_model as m  # noqa: E402

RUNS = 5
HEADER = """use ingot::escrow::CAP
use ingot::escrow_explore::{explore, explore_seeds, counterexample, LOCKED_BASE, LOCKED_STRIDE}
use ingot::vault::{VB, VT}
use ingot::vault_explore::{vexplore, vcounterexample}
"""


def sh(cmd, cwd, timeout=900):
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t0


def make_copy():
    d = Path(tempfile.mkdtemp(prefix="exhaust-bench-"))
    shutil.copy(ROOT / "fe.toml", d)
    shutil.copytree(ROOT / "src", d / "src")
    for f in ("escrow_explore.fe", "vault_explore.fe"):  # gate-stripped: only the probe's asserts run
        p = d / "src" / f
        t = p.read_text()
        p.write_text(t[: t.index("// ---- pins")])
    return d


def check(d, body, runs=RUNS):
    """Write the probe, run `fe check` `runs` times. Returns (status, median wall s)."""
    (d / "src" / "bench_probe.fe").write_text(HEADER + body + "\n")
    times, status = [], None
    for _ in range(runs):
        rc, out, dt = sh(["fe", "check"], d)
        times.append(dt)
        s = "pass" if rc == 0 else "step-limit" if "step limit" in out else "mismatch" if "left:" in out else "error"
        if status not in (None, s):
            status = "unstable"
        else:
            status = s
        if s != "pass" and runs > 1:
            break
    return status, round(statistics.median(times), 3)


def cpu():
    if platform.system() == "Darwin":
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def run_test(filter_, backend=None):
    cmd = ["fe", "test", "--filter", filter_, "--show-logs"] + (["--backend", backend] if backend else [])
    rc, out, dt = sh(cmd, ROOT)
    return rc, out, round(dt, 3)


def gas_of(out):
    m_ = re.search(r"data: 0x([0-9a-f]{128})", out)
    if not m_:
        return None
    return int(m_.group(1)[:64], 16), int(m_.group(1)[64:], 16)


def main():
    skip_budget = "--skip-budget" in sys.argv
    date = time.strftime("%Y-%m-%d", time.gmtime())
    if "--date" in sys.argv:
        date = sys.argv[sys.argv.index("--date") + 1]
    fe = subprocess.run(["fe", "--version"], capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    meta = {"date_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime()), "fe": fe, "commit": commit + ("+dirty-src" if dirty else ""),
            "uname": " ".join(platform.uname()), "cpu": cpu(), "python": platform.python_version(), "fe_check_runs_per_row": RUNS}
    d = make_copy()
    out = {"meta": meta}

    # (0) the cost of compiling the ingot with no probe: subtract it to read a row as search time
    (d / "src" / "bench_probe.fe").write_text(HEADER + "\n")
    base = statistics.median(sh(["fe", "check"], d)[2] for _ in range(RUNS))
    out["baseline_fe_check_s"] = round(base, 3)
    print(f"baseline fe check (gate-stripped ingot, no probe): {base:.3f} s", flush=True)

    # (1) escrow capacity sweep
    sweep = []
    for c in (2, 4, 8, 12, 16, 17, 18, 19, 20, 21):
        r = m.search(c)
        status, wall = check(d, f"static_assert(explore({c}) == {r['states']})")
        # the attack printer is a full search with four tables: it fits only at the lower capacities
        cstatus, cwall = check(d, f"static_assert(counterexample({c}) == 0)", runs=1)
        sweep.append({"cap": c, "states": r["states"], "edges": r["edges"], "attempts": r["attempts"], "diameter": r["diameter"],
                      "explore_status": status, "explore_fe_check_median_s": wall,
                      "counterexample_status": cstatus, "counterexample_fe_check_s": cwall})
        print("escrow", sweep[-1], flush=True)
    out["escrow_sweep"] = sweep

    # (2) step budget
    if not skip_budget:
        rc, o, dt = sh([sys.executable, str(ROOT / "bench" / "budget_probe.py")], ROOT, timeout=1800)
        if rc != 0:
            sys.exit("budget_probe failed:\n" + o[-2000:])
    out["step_budget"] = json.loads((ROOT / "evidence" / "budget.json").read_text())

    # (3) shard scaling: the locked-amount seeds k = 1..21 split into n contiguous groups, one static_assert each
    shards = []
    stride = m.W * m.W
    for n in (1, 2, 4, 8):
        k = 21
        sizes = [k // n + (1 if i < k % n else 0) for i in range(n)]
        lo, body, per = 1, "", []
        for sz in sizes:
            hi = lo + sz - 1
            got = len(m.reach([(m.LOCKED, kk, 0, 0) for kk in range(lo, hi + 1)], m.MAX_CAP))
            body += f"static_assert(explore_seeds(LOCKED_BASE + {lo} * LOCKED_STRIDE, {sz}, LOCKED_STRIDE, CAP) == {got})\n"
            per.append(got)
            lo = hi + 1
        status, wall = check(d, body)
        shards.append({"shards": n, "states_per_shard": per, "largest_shard_states": max(per), "status": status, "fe_check_median_s": wall})
        print("shards", shards[-1], flush=True)
    out["shard_scaling"] = shards

    # (4) runtime search: gas on the EVM backend, time on the native backend
    runtime = {}
    for name, flt, nat in (("escrow C=17", "test_runtime_search_gas", "test_runtime_explore_agrees"),
                           ("vault B=10 T=3", "test_vault_runtime_search_gas", "test_vault_runtime_agrees")):
        rc, o, wall = run_test(flt)
        g = gas_of(o)
        rc2, o2, wall2 = run_test(nat, "native")
        runtime[name] = {"evm_gas": None if g is None else g[0], "states": None if g is None else g[1], "evm_test_ok": rc == 0,
                         "evm_fe_test_wall_s": wall, "native_test_ok": rc2 == 0, "native_fe_test_wall_s": wall2}
        print("runtime", name, runtime[name], flush=True)
    out["runtime_search"] = runtime

    # (5) the vault
    vault = []
    for b, t in ((8, 2), (10, 1), (10, 2), (10, 3)):
        r = m.vsearch(b, t)
        status, wall = check(d, f"static_assert(vexplore({b}, {t}) == {r['states']})")
        row = {"b": b, "t": t, "states": r["states"], "edges": r["edges"], "attempts": r["attempts"], "diameter": r["diameter"],
               "explore_status": status, "explore_fe_check_median_s": wall}
        if (b, t) == (10, 3):
            row["counterexample_status"], row["counterexample_fe_check_s"] = check(d, "static_assert(vcounterexample(VB, VT) == 0)", runs=1)
        vault.append(row)
        print("vault", row, flush=True)
    for b, t in ((12, 3), (16, 3)):  # beyond the encoding: not searchable (MAX_B = 10)
        vault.append({"b": b, "t": t, "note": "outside the encoding (MAX_B = 10): not searched"})
    out["vault"] = vault
    out["vault_contract_graph"] = {k: m.vcontract_graph(10, 3, k == "ready") for k in ("ready", "locked")}
    shutil.rmtree(d)

    (ROOT / "evidence" / f"bench-{date}.json").write_text(json.dumps(out, indent=1) + "\n")
    L = [f"# Benchmarks ({date}) — written by bench/run.py", "",
         f"{meta['date_utc']} UTC · `{fe}` · commit `{meta['commit']}` · `{meta['uname']}` · {meta['cpu']} · python {meta['python']}", "",
         "Counts are exact (Python oracle `tools/ref_model.py`); a `pass` row means the Fe compile-time search returned the same count.",
         f"Wall times are the median of {RUNS} `fe check` runs of the whole ingot, which includes compiling everything else:",
         f"the gate-stripped ingot with no probe takes **{out['baseline_fe_check_s']} s** on its own. Times vary by machine; counts do not.", "",
         "## 1. Escrow capacity sweep (`explore(C)`, one static_assert each; the attack printer `counterexample(C)` is one run)", "",
         "| C | states | edges | attempts | diameter | `explore(C)` | fe check median (s) | `counterexample(C)` |", "|---:|---:|---:|---:|---:|---|---:|---|"]
    for r in sweep:
        L.append(f"| {r['cap']} | {r['states']} | {r['edges']} | {r['attempts']} | {r['diameter']} | {r['explore_status']} | "
                 f"{r['explore_fe_check_median_s']} | {r['counterexample_status']} |")
    L += ["", "Capacities above 21 do not fit the encoding (`MAX_CAP = 21`), so C = 22 is not a step-limit row but an encoding limit.", "",
          "## 2. Step budget", "",
          "Measured by `bench/budget_probe.py` (loop bisection, see `evidence/budget.md`): the per-assert limit is 1,000,000 evaluator steps.", "",
          "| search | states | steps | share of 1M | steps per state |", "|---|---:|---:|---:|---:|"]
    for r in out["step_budget"]["rows"]:
        L.append(f"| `{r['expr']}` | {r['states']} | {'over limit' if r['steps'] is None else f'{r['steps']:,}'} | "
                 f"{'—' if r['share_of_limit'] is None else f'{100 * r['share_of_limit']:.1f}%'} | "
                 f"{'—' if r['steps_per_state_after_setup'] is None else f'{r['steps_per_state_after_setup']:,}'} |")
    L += ["", "## 3. Shard scaling (performance only: seeds k = 1..21 of the locked amount split over n independent static_asserts)", "",
          "| shards | states per shard | largest shard | status | fe check median (s) |", "|---:|---|---:|---|---:|"]
    for r in shards:
        L.append(f"| {r['shards']} | {', '.join(map(str, r['states_per_shard']))} | {r['largest_shard_states']} | {r['status']} | {r['fe_check_median_s']} |")
    L += ["", "Independent asserts each get their own 1,000,000-step budget, so the largest shard is what has to fit; the compiler runs them one after another, so the wall time does not fall with more shards.", "",
          "## 4. Runtime search (the same explorer, run at runtime)", "",
          "| model | EVM gas (Sonatina, `fe test`) | states | EVM test ok | native `fe test` wall (s, incl. compile) | native test ok |", "|---|---:|---:|---|---:|---|"]
    for k, r in runtime.items():
        L.append(f"| {k} | {r['evm_gas']:,} | {r['states']} | {r['evm_test_ok']} | {r['native_fe_test_wall_s']} | {r['native_test_ok']} |")
    L += ["", "## 5. Vault (2-of-3 approval + timelock)", "",
          "| B | T | states | edges | attempts | diameter | `vexplore(B, T)` | fe check median (s) | `vcounterexample` |", "|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for r in vault:
        if "note" in r:
            L.append(f"| {r['b']} | {r['t']} | — | — | — | — | {r['note']} | — | — |")
        else:
            L.append(f"| {r['b']} | {r['t']} | {r['states']} | {r['edges']} | {r['attempts']} | {r['diameter']} | {r['explore_status']} | "
                     f"{r['explore_fe_check_median_s']} | {r.get('counterexample_status', '—')} |")
    g = out["vault_contract_graph"]
    L += ["", f"The deployed vault walks a smaller graph than the model (no Tick handler, the harness cannot move time or change the caller): "
          f"{g['ready']['states']} states / {g['ready']['edges']} edges with the lock passed, {g['locked']['states']} / {g['locked']['edges']} with a lock that never passes (B = 10, T = 3).", ""]
    (ROOT / "evidence" / f"bench-{date}.md").write_text("\n".join(L))
    print(f"wrote evidence/bench-{date}.json and .md")


if __name__ == "__main__":
    main()
